from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest

from gha_assistant import agent

Output = dict[str, Any]

# Line 1 exists in every file the tests create; no quote, so it needs no particular content.
STUB_OUTPUT: Output = {"findings": [{"severity": "low", "message": "stub remark", "line": 1}]}


@dataclass
class FakeAgent:
    """Stand-in for `agent.run_agent`: records every call, answers from `respond`.

    `respond` gets the call's keyword arguments and returns the structured output, or
    raises (an `Exception` instance it returns is raised too, for one-liners).
    """

    respond: Callable[[dict[str, Any]], Output | Exception] = lambda call: STUB_OUTPUT
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run_agent(self, **kwargs: Any) -> Output:
        self.calls.append(kwargs)
        result = self.respond(kwargs)
        if isinstance(result, Exception):
            raise result
        return result

    def calls_for(self, path: str) -> list[dict[str, Any]]:
        """Calls made for one file (`review_code` puts it on the first prompt line)."""
        return [c for c in self.calls if c["prompt"].startswith(f"File: {path}\n")]


def install(monkeypatch: pytest.MonkeyPatch) -> FakeAgent:
    fake = FakeAgent()
    monkeypatch.setattr(agent, "run_agent", fake.run_agent)
    return fake
