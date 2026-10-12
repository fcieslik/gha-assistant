import asyncio
from pathlib import Path
from typing import Any, TypedDict

from gha_assistant import agent
from gha_assistant.change import file_diff
from gha_assistant.finding import Finding
from gha_assistant.state import ReviewState

# A generated or vendored file can have a huge diff; past this the tail is cut and the
# model is told so, rather than failing the whole attempt on the context limit.
MAX_DIFF_CHARS = 60_000

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
