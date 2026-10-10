from pathlib import Path

from gha_assistant.change import collect_change
from gha_assistant.state import ReviewState


def collect_input(state: ReviewState) -> ReviewState:
    print("collect_input: hello world")
    return {"change": collect_change(state["base_ref"], Path(state["repo_path"]))}
