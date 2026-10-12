from typing import TypedDict

from gha_assistant.finding import Finding, Verdict
from gha_assistant.state import ReviewState


class VerifyFindingInput(TypedDict):
    """Private payload of one `Send`: one Finding."""

    finding: Finding


async def verify_finding(payload: VerifyFindingInput) -> ReviewState:
    # Stub: every Finding is confirmed.
    verdict: Verdict = {
        "finding_id": payload["finding"]["id"],
        "verdict": "confirmed",
        "reason": "stub verdict",
    }
    return {"verdicts": [verdict]}
