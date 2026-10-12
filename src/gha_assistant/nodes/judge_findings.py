from gha_assistant.state import ReviewState


async def judge_findings(state: ReviewState) -> ReviewState:
    # Stub: keeps every Finding, including the ones that were not verified.
    return {"findings": list(state.get("validated", [])), "summary": "stub summary"}
