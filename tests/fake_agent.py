from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest

from gha_assistant import agent

Output = dict[str, Any]

# Line 1 exists in every file the tests create; no quote, so it needs no particular content.
STUB_OUTPUT: Output = {"findings": [{"severity": "low", "message": "stub remark", "line": 1}]}
# `review_intent` answers in another shape: a general remark that points at an Intent file.
STUB_INTENT_OUTPUT: Output = {
    "findings": [
        {"severity": "medium", "message": "stub remark about the intent", "spec_ref": "spec.md"}
    ]
}
# `verify_finding` answers with a verdict, not with Findings.
STUB_VERIFY_OUTPUT: Output = {"verdict": "confirmed", "reason": "stub verdict"}


def is_verify(call: dict[str, Any]) -> bool:
    return str(call.get("label", "")).startswith("verify_finding")


def default_response(call: dict[str, Any]) -> Output:
    return STUB_INTENT_OUTPUT if call.get("label") == "review_intent" else STUB_OUTPUT


def default_verify_response(call: dict[str, Any]) -> Output:
    return STUB_VERIFY_OUTPUT


@dataclass
class FakeAgent:
    """Stand-in for `agent.run_agent`: records every call, answers from `respond`.

    `respond` answers the reviewers and `respond_verify` the verifiers (their answers have
    another shape, so a test that scripts the reviewers does not have to know about them).
    Each gets the call's keyword arguments and returns the structured output, or raises
    (an `Exception` instance it returns is raised too, for one-liners).
    """

    respond: Callable[[dict[str, Any]], Output | Exception] = default_response
    respond_verify: Callable[[dict[str, Any]], Output | Exception] = default_verify_response
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run_agent(self, **kwargs: Any) -> Output:
        self.calls.append(kwargs)
        result = (self.respond_verify if is_verify(kwargs) else self.respond)(kwargs)
        if isinstance(result, Exception):
            raise result
        return result

    def intent_calls(self) -> list[dict[str, Any]]:
        return [c for c in self.calls if c.get("label") == "review_intent"]

    def verify_calls(self) -> list[dict[str, Any]]:
        return [c for c in self.calls if is_verify(c)]

    def calls_for(self, path: str) -> list[dict[str, Any]]:
        """Calls made for one file (`review_code` puts it on the first prompt line)."""
        return [c for c in self.calls if c["prompt"].startswith(f"File: {path}\n")]


def install(monkeypatch: pytest.MonkeyPatch) -> FakeAgent:
    fake = FakeAgent()
    monkeypatch.setattr(agent, "run_agent", fake.run_agent)
    return fake
