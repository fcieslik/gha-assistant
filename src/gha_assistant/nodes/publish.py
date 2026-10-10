from gha_assistant.state import ReviewState


def publish(state: ReviewState) -> ReviewState:
    print("publish: hello world")
    return {}
