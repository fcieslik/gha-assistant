import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from gitrepo import GitRepo

from gha_assistant import change as change_module
from gha_assistant.change import _parse_name_status, collect_change, file_diff

FIXTURES = Path(__file__).parent / "fixtures" / "name_status"

EXPECTED = {
    "modified": {"intent": [], "code": ["src/app.py"], "ignored": []},
    "added": {"intent": [], "code": ["src/new.py"], "ignored": []},
    "deleted": {"intent": [], "code": [], "ignored": ["src/old.py"]},
    "renamed": {"intent": [], "code": ["src/new_name.py"], "ignored": []},
    "empty": {"intent": [], "code": [], "ignored": []},
    "multi_pattern": {
        "intent": ["docs/adr/0001.md", "docs/adr/0002.md"],
        "code": ["src/app.py"],
        "ignored": [".scratch/f/spec.md", "dist/app.min.js", "docs/adr/old.md"],
    },
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


@pytest.mark.parametrize(
    ("path", "bucket"),
    [
        ("src/app.py", "code"),
        (".scratch/change-collection/spec.md", "intent"),
        (".scratch/change-collection/issues/02-ticket.md", "intent"),
        ("docs/adr/0001-decision.md", "intent"),
        ("README.md", "ignored"),
        ("CONTEXT.md", "ignored"),
        ("docs/agents/issue-tracker.md", "ignored"),
        ("uv.lock", "ignored"),
        ("frontend/package-lock.json", "ignored"),
        ("pnpm-lock.yaml", "ignored"),
        ("assets/logo.PNG", "ignored"),
        ("dist/bundle.js", "ignored"),
        ("web/dist/bundle.js", "ignored"),
        ("static/app.min.js", "ignored"),
    ],
)
def test_added_file_is_classified(
    git_repo: Callable[[str], GitRepo],
    path: str,
    bucket: str,
) -> None:
    repo = git_repo("pr")
    repo.write("base.txt", "base\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)

    repo.git("switch", "-c", "pr")
    repo.write(path, "content\n")
    repo.commit("pr")

    change = collect_change("origin/main", repo.path)

    assert change[bucket] == [path]
    assert sum(len(paths) for paths in change.values()) == 1


def test_deleted_intent_file_is_ignored(git_repo: Callable[[str], GitRepo]) -> None:
    repo = git_repo("pr")
    repo.write("docs/adr/0001-decision.md", "decision\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)

    repo.git("switch", "-c", "pr")
    repo.git("rm", "-q", "docs/adr/0001-decision.md")
    repo.commit("pr")

    assert collect_change("origin/main", repo.path) == {
        "intent": [],
        "code": [],
        "ignored": ["docs/adr/0001-decision.md"],
    }


def test_renamed_file_counts_under_new_path(git_repo: Callable[[str], GitRepo]) -> None:
    repo = git_repo("pr")
    repo.write("src/old_name.py", "print('same content, long enough to be a rename')\n")
    repo.write("docs/adr/.keep", "")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)

    repo.git("switch", "-c", "pr")
    repo.git("mv", "src/old_name.py", "docs/adr/0002-renamed.md")
    repo.commit("pr")

    assert collect_change("origin/main", repo.path) == {
        "intent": ["docs/adr/0002-renamed.md"],
        "code": [],
        "ignored": [],
    }


def test_base_ref_that_looks_like_an_option_is_rejected(
    git_repo: Callable[[str], GitRepo], tmp_path: Path
) -> None:
    repo = git_repo("pr")
    repo.write("src/app.py", "print('hi')\n")
    repo.commit("base")
    pwned = tmp_path / "pwned"

    with pytest.raises(ValueError, match="base_ref"):
        collect_change(f"--output={pwned}", repo.path)

    assert not pwned.exists()


def test_empty_base_ref_is_rejected(git_repo: Callable[[str], GitRepo]) -> None:
    repo = git_repo("pr")

    with pytest.raises(ValueError, match="base_ref"):
        collect_change("", repo.path)


def test_git_diff_runs_with_a_timeout(
    git_repo: Callable[[str], GitRepo], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = git_repo("pr")
    seen: dict[str, Any] = {}

    def hanging_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs)
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr(change_module.subprocess, "run", hanging_run)

    with pytest.raises(subprocess.TimeoutExpired):
        collect_change("origin/main", repo.path)

    assert seen["timeout"] == change_module.GIT_TIMEOUT_SECONDS


def test_file_diff_is_limited_to_one_file_and_to_the_pr_changes(
    git_repo: Callable[[str], GitRepo],
) -> None:
    repo = git_repo("pr")
    repo.write("src/a.py", "a = 1\n")
    repo.write("src/b.py", "b = 1\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)
    repo.git("switch", "-c", "pr")
    repo.write("src/a.py", "a = 2\n")
    repo.write("src/b.py", "b = 2\n")
    repo.commit("pr")

    diff = file_diff("origin/main", repo.path, "src/a.py")

    assert "-a = 1" in diff
    assert "+a = 2" in diff
    assert "b = " not in diff


def test_file_diff_rejects_a_base_ref_that_looks_like_an_option(
    git_repo: Callable[[str], GitRepo], tmp_path: Path
) -> None:
    repo = git_repo("pr")
    repo.write("src/a.py", "a = 1\n")
    repo.commit("base")

    with pytest.raises(ValueError):
        file_diff(f"--output={tmp_path / 'pwned'}", repo.path, "src/a.py")

    assert not (tmp_path / "pwned").exists()
