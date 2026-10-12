import subprocess
from pathlib import Path
from typing import Literal

from langgraph.types import Command, RetryPolicy, Send

from gha_assistant.change import Change, collect_change
from gha_assistant.state import ReviewState

# Git reports lock contention with these phrases; every other git failure
# (bad ref, not a repo) is permanent and must fail fast.
_TRANSIENT_GIT_MARKERS = (
    "index.lock",
    "another git process",
    "resource temporarily unavailable",
)


def is_transient_git_error(exc: Exception) -> bool:
    """Whether `exc` is a git failure worth retrying.

    LangGraph's default `retry_on` would also retry any `CalledProcessError`,
    including a bad `base_ref` that can never succeed.
    """
    if not isinstance(exc, subprocess.CalledProcessError):
        return False
    stderr = (exc.stderr or "").lower()
    return any(marker in stderr for marker in _TRANSIENT_GIT_MARKERS)


COLLECT_INPUT_RETRY = RetryPolicy(max_attempts=3, retry_on=is_transient_git_error)


def next_step(
    change: Change, base_ref: str, repo_path: str
) -> Literal["nothing_to_review"] | list[str | Send]:
    """Where the graph goes once the Change is known.

    Docs, lockfiles, binaries and Intent files alone leave no code to review.
    Otherwise it fans out: one `review_code` per code file, and `review_intent` once
    (it reads shared state, so it needs no `Send`) when there are Intent files. A worker
    gets its file plus the two paths needed to read that file's diff, not the whole state.
    """
    if not change["code"]:
        return "nothing_to_review"
    steps: list[str | Send] = [
        Send("review_code", {"path": path, "base_ref": base_ref, "repo_path": repo_path})
        for path in change["code"]
    ]
    if change["intent"]:
        steps.append("review_intent")
    return steps


def collect_input(
    state: ReviewState,
) -> Command[Literal["review_code", "review_intent", "nothing_to_review"]]:
    missing = [key for key in ("base_ref", "repo_path") if not state.get(key)]
    if missing:
        raise ValueError(f"collect_input requires: {', '.join(missing)}")
    change = collect_change(state["base_ref"], Path(state["repo_path"]))
    return Command(
        update={"change": change}, goto=next_step(change, state["base_ref"], state["repo_path"])
    )
