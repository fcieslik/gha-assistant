from collections.abc import Callable
from pathlib import Path

import pytest
from gitrepo import GitRepo

from gha_assistant.change import _parse_name_status, collect_change

FIXTURES = Path(__file__).parent / "fixtures" / "name_status"

EXPECTED = {
    "modified": {"intent": [], "code": ["src/app.py"], "ignored": []},
    "added": {"intent": [], "code": ["src/new.py"], "ignored": []},
    "deleted": {"intent": [], "code": [], "ignored": ["src/old.py"]},
    "renamed": {"intent": [], "code": ["src/new_name.py"], "ignored": []},
    "empty": {"intent": [], "code": [], "ignored": []},
}


@pytest.mark.parametrize("name", EXPECTED)
def test_parse_name_status_fixture(name: str) -> None:
    text = (FIXTURES / f"{name}.txt").read_text()

    assert _parse_name_status(text) == EXPECTED[name]


def test_three_dot_diff_ignores_base_commits_made_after_merge(
    git_repo: Callable[[str], GitRepo],
) -> None:
    repo = git_repo("pr")
    repo.write("src/app.py", "print('before')\n")
    repo.write("src/keep.py", "print('keep')\n")
    base = repo.commit("base")

    repo.git("switch", "-c", "pr")
    repo.write("src/app.py", "print('after')\n")
    repo.write("src/new.py", "print('new')\n")
    repo.commit("pr")

    # The merge commit that CI checks out: base plus PR, with base as its first parent.
    repo.git("switch", "main")
    repo.git("merge", "--no-ff", "-m", "merge pr", "pr")
    merge = repo.git("rev-parse", "HEAD")

    # The base then moves on from `base`, touching a file the PR does not touch.
    repo.git("switch", "--detach", base)
    repo.write("src/base_only.py", "print('moved on')\n")
    base_next = repo.commit("base moves on")
    repo.git("update-ref", "refs/remotes/origin/main", base_next)
    repo.git("switch", "--detach", merge)

    assert collect_change("origin/main", repo.path) == {
        "intent": [],
        "code": ["src/app.py", "src/new.py"],
        "ignored": [],
    }
