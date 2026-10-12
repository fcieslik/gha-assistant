import asyncio
import operator
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.types import RetryPolicy

from gha_assistant import agent
from gha_assistant.change import file_diff
from gha_assistant.finding import Finding
from gha_assistant.limits import MAX_DIFF_CHARS
from gha_assistant.nodes.degradable import compile_attempt
from gha_assistant.state import ReviewState

SYSTEM_PROMPT = agent.load_prompt("review_code")

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"enum": ["low", "medium", "high"]},
                    "message": {"type": "string"},
                    "line": {"type": "integer"},
                    "evidence": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["severity", "message", "line", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}


class ReviewCodeInput(TypedDict):
    """Private payload of one `Send`: the worker sees one file, not the whole state."""

    path: str
    base_ref: str
    repo_path: str


class _CodeState(ReviewCodeInput, total=False):
    """State of the one-node graph an attempt runs in (see `make_review_code`)."""

    candidates: Annotated[list[Finding], operator.add]
    warnings: Annotated[list[str], operator.add]


def build_prompt(path: str, diff: str) -> str:
    note = ""
    if len(diff) > MAX_DIFF_CHARS:
        diff, note = diff[:MAX_DIFF_CHARS], "\n(diff truncated; read the file for the rest)"
    return f'File: {path}\n<diff path="{path}">\n{diff}{note}\n</diff>'


def to_findings(path: str, output: dict[str, Any]) -> list[Finding]:
    """Findings from the model's answer; `source` and `id` are set here, never by the model."""
    findings: list[Finding] = []
    for index, item in enumerate(output["findings"], start=1):
        finding: Finding = {
            "id": f"code:{path}:{item['line']}:{index}",
            "source": "code",
            "severity": item["severity"],
            "message": item["message"],
            "file": path,
            "line": item["line"],
        }
        if item.get("evidence"):
            finding["evidence"] = item["evidence"]
        if item.get("suggestion"):
            finding["suggestion"] = item["suggestion"]
        findings.append(finding)
    return findings


async def review_code(payload: ReviewCodeInput) -> ReviewState:
    path, repo_path = payload["path"], payload["repo_path"]
    diff = await asyncio.to_thread(file_diff, payload["base_ref"], Path(repo_path), path)
    output = await agent.run_agent(
        model=agent.REVIEW_MODEL,
        system_prompt=SYSTEM_PROMPT,
        prompt=build_prompt(path, diff),
        output_schema=OUTPUT_SCHEMA,
        cwd=repo_path,
        label=f"review_code {path}",
    )
    return {"candidates": to_findings(path, output)}


def degrade(state: _CodeState, exc: Exception) -> _CodeState:
    """What is left of one file's review once its retries are used up: a warning, so the
    other files' remarks stay."""
    return {
        "warnings": [
            f"review_code nie powiódł się mimo ponowień ({type(exc).__name__}): "
            f"plik {state['path']} nie został sprawdzony"
        ]
    }


def make_review_code(
    retry_policy: RetryPolicy, timeout: float
) -> Callable[[ReviewCodeInput], Awaitable[ReviewState]]:
    """The `review_code` node: `review_code` above is one attempt, run with the retry
    policy, the timeout and a warning instead of a failed run."""
    compiled = compile_attempt(_CodeState, review_code, degrade, retry_policy, timeout)

    async def review_code_with_degradation(payload: ReviewCodeInput) -> ReviewState:
        result = await compiled.ainvoke(
            {
                "path": payload["path"],
                "base_ref": payload["base_ref"],
                "repo_path": payload["repo_path"],
            }
        )
        # Only what the attempt produced: the nested graph started with empty
        # `candidates` and `warnings`, so these are the new ones.
        return {
            "candidates": result.get("candidates", []),
            "warnings": result.get("warnings", []),
        }

    return review_code_with_degradation
