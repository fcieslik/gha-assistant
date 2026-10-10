from gha_assistant.state import ReviewState


def run_agent(state: ReviewState) -> ReviewState:
    print("run_agent: hello world")
    return {"summary": "stub summary"}
