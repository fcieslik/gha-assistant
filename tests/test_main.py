import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import ResultError
from fake_agent import FakeAgent
from fake_github import FakeGitHub
from gitrepo import GitRepo

from gha_assistant.__main__ import main

HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"


def _pr_repo(git_repo: Callable[[str], GitRepo]) -> GitRepo:
    repo = git_repo("pr")
    repo.write("src/app.py", "print('before')\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)
    repo.git("switch", "-c", "pr")
    repo.write("src/app.py", "print('after')\n")
    repo.commit("pr")
    return repo


def _event(tmp_path: Path, **pull_request: Any) -> str:
    pr: dict[str, Any] = {
        "number": 7,
        "title": "Zmiana",
        "body": None,  # GitHub sends null for an empty description
        "base": {"ref": "main", "repo": {"full_name": "octo/repo"}},
        "head": {"sha": HEAD_SHA, "repo": {"full_name": "octo/repo"}},
    }
    pr.update(pull_request)
    path = tmp_path / "event.json"
    path.write_text(json.dumps({"pull_request": pr}))
    return str(path)


def _env(event_path: str | None, **extra: str) -> dict[str, str]:
    env = {
        "GITHUB_ACTIONS": "true",
        "GITHUB_REPOSITORY": "octo/repo",
        "ANTHROPIC_API_KEY": "sk-test",
    }
    if event_path:
        env["GITHUB_EVENT_PATH"] = event_path
    return {**env, **extra}


def test_pull_request_event_gets_one_comment_with_the_findings(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub, tmp_path: Path
) -> None:
    repo = _pr_repo(git_repo)

    code = main(["--repo-path", str(repo.path)], _env(_event(tmp_path)))

    assert code == 0
    (comment,) = fake_github.comments
    assert (comment["repo"], comment["pr"]) == ("octo/repo", 7)
    body = comment["body"]
    assert "sprawdzono plików: 1, uwagi: 1" in body
    assert "- **low** `src/app.py:1`" in body
    assert "stub remark" in body
    assert HEAD_SHA[:7] in body


def test_the_workspace_variable_says_where_the_checkout_is(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    fake_agent: FakeAgent,
    tmp_path: Path,
) -> None:
    repo = _pr_repo(git_repo)

    code = main([], _env(_event(tmp_path), GITHUB_WORKSPACE=str(repo.path)))

    assert code == 0
    assert {call["cwd"] for call in fake_agent.calls} == {str(repo.path)}


def test_title_and_description_reach_the_intent_reviewer(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    fake_agent: FakeAgent,
    tmp_path: Path,
) -> None:
    repo = _pr_repo(git_repo)
    repo.write(".scratch/f/spec.md", "# Spec\n")
    repo.commit("spec")

    code = main(
        ["--repo-path", str(repo.path)],
        _env(_event(tmp_path, title="Dodaj raport", body="Opis zmiany")),
    )

    assert code == 0
    (call,) = fake_agent.intent_calls()
    assert "Dodaj raport" in call["prompt"]
    assert "Opis zmiany" in call["prompt"]


def test_dry_run_prints_the_comment_and_posts_nothing(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _pr_repo(git_repo)

    code = main(["--dry-run", "--repo-path", str(repo.path)], _env(_event(tmp_path)))

    assert code == 0
    assert "**gha-assistant:**" in capsys.readouterr().out
    assert fake_github.requests == []


def test_local_dry_run_needs_no_event(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _pr_repo(git_repo)

    code = main(
        ["--dry-run", "--base-ref", "origin/main", "--repo-path", str(repo.path)],
        _env(None),
    )

    assert code == 0
    assert "sprawdzono plików: 1" in capsys.readouterr().out
    assert fake_github.requests == []


def test_without_an_event_a_real_run_is_refused(
    fake_github: FakeGitHub, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main(["--base-ref", "origin/main"], _env(None))

    assert code == 2
    assert "--dry-run" in capsys.readouterr().err
    assert fake_github.requests == []


def test_an_event_without_a_pull_request_is_refused(
    fake_github: FakeGitHub, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    push = tmp_path / "push.json"
    push.write_text(json.dumps({"ref": "refs/heads/main"}))

    code = main([], _env(str(push)))

    assert code == 2
    assert "pull_request" in capsys.readouterr().err
    assert fake_github.requests == []


def test_missing_key_is_a_readable_error_before_any_work(
    fake_github: FakeGitHub,
    fake_agent: FakeAgent,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env = _env(_event(tmp_path))
    del env["ANTHROPIC_API_KEY"]

    code = main([], env)

    assert code == 2
    assert capsys.readouterr().err.startswith("::error::gha-assistant: ANTHROPIC_API_KEY")
    assert fake_agent.calls == []
    assert fake_github.requests == []


def test_pr_from_a_fork_is_skipped_without_an_error(
    fake_github: FakeGitHub, fake_agent: FakeAgent, tmp_path: Path
) -> None:
    event = _event(tmp_path, head={"sha": HEAD_SHA, "repo": {"full_name": "someone/repo"}})
    env = _env(event)
    del env["ANTHROPIC_API_KEY"]  # a fork run has no secrets

    code = main([], env)

    assert code == 0
    assert fake_agent.calls == []
    assert fake_github.requests == []


def test_a_failed_run_is_a_readable_error_and_exit_code_one(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    fake_agent: FakeAgent,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _pr_repo(git_repo)
    fake_agent.respond = lambda call: ResultError(
        "Invalid API key · Fix external API key",
        data={"subtype": "success", "api_error_status": 401, "terminal_reason": "api_error"},
        exit_code=1,
    )

    code = main(["--repo-path", str(repo.path)], _env(_event(tmp_path)))

    assert code == 1
    first_line = capsys.readouterr().err.splitlines()[0]
    assert first_line.startswith("::error::gha-assistant: ResultError: Invalid API key")
    assert fake_github.comments == []


def test_outside_actions_the_error_has_no_annotation_prefix(
    fake_github: FakeGitHub, capsys: pytest.CaptureFixture[str]
) -> None:
    env = _env(None)
    del env["GITHUB_ACTIONS"]

    main([], env)

    assert capsys.readouterr().err.startswith("error: gha-assistant:")
