from typing import TypedDict

from gha_assistant.change import Change


class ReviewState(TypedDict, total=False):
    base_ref: str
    repo_path: str
    pr_title: str
    pr_body: str
    change: Change
    summary: str
