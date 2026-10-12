from gha_assistant.github_io import no_code_status, publish_status_comment
from gha_assistant.state import ReviewState


def nothing_to_review(state: ReviewState) -> ReviewState:
    change = state["change"]
    ignored, intent = len(change["ignored"]), len(change["intent"])
    print(f"nothing_to_review: no code to review ({ignored} ignored, {intent} intent)")
    publish_status_comment(state, no_code_status(ignored, intent))
    return {}
