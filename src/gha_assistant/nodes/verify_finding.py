import json
import operator
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypedDict

from langgraph.types import RetryPolicy

from gha_assistant import agent
from gha_assistant.finding import Finding, Verdict
from gha_assistant.nodes.degradable import compile_attempt
from gha_assistant.state import ReviewState

SYSTEM_PROMPT = agent.load_prompt("verify_finding")

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"enum": ["confirmed", "refuted", "inconclusive"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}


class VerifyFindingInput(TypedDict):
    """Private payload of one `Send`: one Finding and where the checkout is."""

    finding: Finding
    repo_path: str


class _VerifyState(VerifyFindingInput, total=False):
    """State of the one-node graph an attempt runs in (see `make_verify_finding`)."""

    verdicts: Annotated[list[Verdict], operator.add]
    warnings: Annotated[list[str], operator.add]


def build_prompt(finding: Finding) -> str:
    """The user message: the Finding as data. `id` is left out, the model does not need it."""
    claim = {key: value for key, value in finding.items() if key != "id"}
    return f"<finding>\n{json.dumps(claim, ensure_ascii=False, indent=2)}\n</finding>"


async def attempt(state: _VerifyState) -> _VerifyState:
    finding = state["finding"]
    output = await agent.run_agent(
        model=agent.VERIFY_MODEL,
        system_prompt=SYSTEM_PROMPT,
        prompt=build_prompt(finding),
        output_schema=OUTPUT_SCHEMA,
        cwd=state["repo_path"],
        label=f"verify_finding {finding['id']}",
    )
    # The id comes from code, never from the model.
    verdict: Verdict = {
        "finding_id": finding["id"],
        "verdict": output["verdict"],
        "reason": output["reason"],
    }
    return {"verdicts": [verdict]}


def degrade(state: _VerifyState, exc: Exception) -> _VerifyState:
    """What is left of one verification once its retries are used up: an `inconclusive`
    verdict and a warning, so the Finding itself is not lost."""
    finding_id = state["finding"]["id"]
    verdict: Verdict = {
        "finding_id": finding_id,
        "verdict": "inconclusive",
        "reason": "Weryfikacja nie powiodła się mimo ponowień.",
    }
    return {
        "verdicts": [verdict],
        "warnings": [
            f"verify_finding nie powiódł się mimo ponowień ({type(exc).__name__}): "
            f"uwaga {finding_id} jest niezweryfikowana"
        ],
    }


def make_verify_finding(
    retry_policy: RetryPolicy, timeout: float
) -> Callable[[VerifyFindingInput], Awaitable[ReviewState]]:
    """The `verify_finding` node: one attempt run with the retry policy, the timeout and
    an `inconclusive` verdict instead of a failed run (see `compile_attempt`)."""
    compiled = compile_attempt(_VerifyState, attempt, degrade, retry_policy, timeout)

    async def verify_finding(payload: VerifyFindingInput) -> ReviewState:
        result = await compiled.ainvoke(
            {"finding": payload["finding"], "repo_path": payload["repo_path"]}
        )
        # Only what the attempt produced: the nested graph started with empty
        # `verdicts` and `warnings`, so these are the new ones.
        return {
            "verdicts": result.get("verdicts", []),
            "warnings": result.get("warnings", []),
        }

    return verify_finding
