import subprocess

import pytest
from langgraph.types import Send

from gha_assistant.change import Change
from gha_assistant.nodes.collect_input import is_transient_git_error, next_step


def _git_failure(stderr: str) -> subprocess.CalledProcessError:
    return subprocess.CalledProcessError(128, ["git", "diff"], stderr=stderr)


@pytest.mark.parametrize(
    "exc",
    [
        _git_failure("fatal: Unable to create '/repo/.git/index.lock': File exists."),
        _git_failure("fatal: Another git process seems to be running in this repository"),
        _git_failure("error: cannot open .git/FETCH_HEAD: Resource temporarily unavailable"),
    ],
)
def test_git_lock_contention_is_transient(exc: Exception) -> None:
    assert is_transient_git_error(exc)


@pytest.mark.parametrize(
    "exc",
    [
        _git_failure("fatal: bad revision 'origin/nope...HEAD'"),
        _git_failure("fatal: not a git repository (or any of the parent directories): .git"),
        subprocess.CalledProcessError(128, ["git", "diff"], stderr=None),
        subprocess.TimeoutExpired(cmd=["git", "diff"], timeout=30),
        FileNotFoundError("git"),
        KeyError("base_ref"),
    ],
)
def test_permanent_failures_are_not_transient(exc: Exception) -> None:
    assert not is_transient_git_error(exc)


# What a `review_code` worker needs besides its file: where to read that file's diff.
WORKER_PAYLOAD = {"base_ref": "origin/main", "repo_path": "/work/pr"}


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            {"intent": [], "code": ["src/app.py"], "ignored": []},
            [Send("review_code", {"path": "src/app.py", **WORKER_PAYLOAD})],
        ),
        (
            {"intent": ["docs/adr/0001-x.md"], "code": ["src/a.py", "src/b.py"], "ignored": []},
            [
                Send("review_code", {"path": "src/a.py", **WORKER_PAYLOAD}),
                Send("review_code", {"path": "src/b.py", **WORKER_PAYLOAD}),
                "review_intent",
            ],
        ),
        ({"intent": [], "code": [], "ignored": ["uv.lock"]}, "nothing_to_review"),
        ({"intent": ["docs/adr/0001-x.md"], "code": [], "ignored": []}, "nothing_to_review"),
        ({"intent": [], "code": [], "ignored": []}, "nothing_to_review"),
    ],
)
def test_next_step_depends_only_on_change(change: Change, expected: object) -> None:
    assert next_step(change, "origin/main", "/work/pr") == expected
