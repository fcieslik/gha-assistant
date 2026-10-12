from typing import Literal

from langgraph.types import Send

from gha_assistant.finding import Finding
from gha_assistant.state import ReviewState

# Verifications are capped; the rest of the Findings go on to the judge unverified.
MAX_VERIFICATIONS = 20

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def validate_findings(state: ReviewState) -> ReviewState:
    # Stub: lets everything through. Pure code, no model.
    return {"validated": list(state.get("candidates", []))}


def route_after_validation(state: ReviewState) -> Literal["publish"] | list[Send]:
    """Next step once the Findings are validated.

    An empty list of `Send` would end the branch and the graph without reaching
    `publish`, so "no Findings" is routed explicitly.
    """
    validated = state.get("validated", [])
    if not validated:
        return "publish"
    return [Send("verify_finding", {"finding": f}) for f in _most_severe_first(validated)]


def _most_severe_first(findings: list[Finding]) -> list[Finding]:
    ranked = sorted(findings, key=lambda f: _SEVERITY_RANK[f["severity"]])
    return ranked[:MAX_VERIFICATIONS]
