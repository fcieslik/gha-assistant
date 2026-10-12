from gha_assistant.finding import Finding
from gha_assistant.state import ReviewState


async def review_intent(state: ReviewState) -> ReviewState:
    # Stub: one general remark (no file, no line), as a failed criterion would be.
    finding: Finding = {
        "id": "spec:1",
        "source": "spec",
        "severity": "medium",
        "message": "stub remark about the intent",
        "spec_ref": state["change"]["intent"][0],
    }
    return {"candidates": [finding]}
