from gha_assistant.state import ReviewState


def collect_input(state: ReviewState) -> ReviewState:
    print("collect_input: hello world")
    return {"diff": "stub diff"}
