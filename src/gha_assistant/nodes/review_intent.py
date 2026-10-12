import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from langgraph.types import RetryPolicy

from gha_assistant import agent
from gha_assistant.change import file_diff
from gha_assistant.finding import Finding
from gha_assistant.limits import (
    MAX_DIFF_CHARS,
    REVIEW_INTENT_MAX_BUDGET_USD,
    REVIEW_INTENT_MAX_TURNS,
)
from gha_assistant.nodes.degradable import compile_attempt
from gha_assistant.state import ReviewState

SYSTEM_PROMPT = agent.load_prompt("review_intent")

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
                    "spec_ref": {"type": "string"},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "evidence": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["severity", "message", "spec_ref"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["findings"],
    "additionalProperties": False,
}

# What the nested graph is given: the one attempt reads nothing else from the state.
_INPUT_KEYS = ("base_ref", "repo_path", "pr_title", "pr_body", "change")


def read_diffs(base_ref: str, repo: Path, paths: list[str]) -> dict[str, str]:
    return {path: file_diff(base_ref, repo, path) for path in paths}


def build_prompt(
    intent: list[str], code: list[str], diffs: dict[str, str], title: str, body: str
) -> str:
    """The user message: the blocks `prompts/review_intent.md` describes.

    Intent files are listed, not inlined: the agent reads them with a tool. The diffs
    share one budget of `MAX_DIFF_CHARS`, because this one run sees every changed file.
    """
    budget = MAX_DIFF_CHARS
    diff_blocks: list[str] = []
    for path in code:
        diff, note = diffs[path], ""
        if len(diff) > budget:
            diff, note = diff[:budget], "\n(diff truncated; read the file for the rest)"
        budget -= len(diff)
        diff_blocks.append(f'<diff path="{path}">\n{diff}{note}\n</diff>')
    return "\n\n".join(
        [
            "<intent_files>\n" + "\n".join(intent) + "\n</intent_files>",
            "<changed_files>\n" + "\n".join(code) + "\n</changed_files>",
            *diff_blocks,
            f"<pr>\nTitle: {title}\n\n{body}\n</pr>",
        ]
    )


def to_findings(output: dict[str, Any]) -> list[Finding]:
    """Findings from the model's answer; `source` and `id` are set here, never by the model."""
    findings: list[Finding] = []
    for index, item in enumerate(output["findings"], start=1):
        finding: Finding = {
            "id": f"spec:{index}",
            "source": "spec",
            "severity": item["severity"],
            "message": item["message"],
            "spec_ref": item["spec_ref"],
        }
        if item.get("file"):
            finding["file"] = item["file"]
        if item.get("line") is not None:
            finding["line"] = item["line"]
        if item.get("evidence"):
            finding["evidence"] = item["evidence"]
        if item.get("suggestion"):
            finding["suggestion"] = item["suggestion"]
        findings.append(finding)
    return findings


async def attempt(state: ReviewState) -> ReviewState:
    change, repo_path = state["change"], state["repo_path"]
    diffs = await asyncio.to_thread(read_diffs, state["base_ref"], Path(repo_path), change["code"])
    prompt = build_prompt(
        change["intent"],
        change["code"],
        diffs,
        state.get("pr_title", ""),
        state.get("pr_body", ""),
    )
    output = await agent.run_agent(
        model=agent.REVIEW_MODEL,
        system_prompt=SYSTEM_PROMPT,
        prompt=prompt,
        output_schema=OUTPUT_SCHEMA,
        max_turns=REVIEW_INTENT_MAX_TURNS,
        max_budget_usd=REVIEW_INTENT_MAX_BUDGET_USD,
        cwd=repo_path,
        label="review_intent",
    )
    return {"candidates": to_findings(output)}


def degrade(state: ReviewState, exc: Exception) -> ReviewState:
    """What is left of `review_intent` once its retries are used up: a warning."""
    return {
        "warnings": [
            f"review_intent nie powiódł się mimo ponowień ({type(exc).__name__}): "
            "review bez uwag o zgodności z Intent files"
        ]
    }


def make_review_intent(
    retry_policy: RetryPolicy, timeout: float
) -> Callable[[ReviewState], Awaitable[ReviewState]]:
    """The `review_intent` node: one attempt run with the retry policy, the timeout and a
    warning instead of a failed run (see `compile_attempt`)."""
    compiled = compile_attempt(ReviewState, attempt, degrade, retry_policy, timeout)

    async def review_intent(state: ReviewState) -> ReviewState:
        given = {key: state[key] for key in _INPUT_KEYS if key in state}
        result = await compiled.ainvoke(given)
        # Only what the attempt produced: the nested graph started with empty
        # `candidates` and `warnings`, so these are the new ones, not a copy of the state.
        return {
            "candidates": result.get("candidates", []),
            "warnings": result.get("warnings", []),
        }

    return review_intent
