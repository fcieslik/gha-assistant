from typing import TypedDict


class ReviewState(TypedDict, total=False):
    diff: str
    summary: str
