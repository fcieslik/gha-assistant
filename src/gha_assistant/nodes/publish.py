from gha_assistant.github_io import publish_status_comment, reviewed_status
from gha_assistant.state import ReviewState


def publish(state: ReviewState) -> ReviewState:
    print("publish: hello world")
    # `findings` is only set by judge_findings; without Findings the judge is skipped.
    findings = len(state.get("findings", []))
    status = reviewed_status(len(state["change"]["code"]), findings=findings)
    # Warnings are shown here and not in `summary`: the judge is skipped when there are
    # no Findings, and that is exactly when a failed reviewer must not look like a clean
    # Review.
    publish_status_comment(
        state, status, summary=state.get("summary", ""), warnings=state.get("warnings", [])
    )
    return {}
