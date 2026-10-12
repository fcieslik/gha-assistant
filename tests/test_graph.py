import asyncio
import subprocess
import urllib.error
from collections.abc import Callable
from email.message import Message
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import ResultError
from fake_agent import FakeAgent
from fake_github import FakeGitHub
from gitrepo import GitRepo

from gha_assistant import agent
from gha_assistant import graph as graph_module
from gha_assistant.change import Change, collect_change
from gha_assistant.graph import build_graph
from gha_assistant.nodes import collect_input as collect_input_module
from gha_assistant.nodes import review_code as review_code_module
from gha_assistant.nodes import validate_findings as validate_findings_module

TARGET = {"repo": "octo/repo", "pr_number": 7, "head_sha": "0123456789abcdef"}


def test_change_reaches_the_final_state(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    repo = git_repo("pr")
    repo.write("src/app.py", "print('before')\n")
    repo.write("src/gone.py", "print('gone')\n")
    repo.write("src/moved.py", "print('moved')\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)

    repo.git("switch", "-c", "pr")
    repo.write("src/app.py", "print('after')\n")
    repo.write("src/added.py", "print('added')\n")
    repo.git("rm", "-q", "src/gone.py")
    repo.git("mv", "src/moved.py", "src/renamed.py")
    repo.commit("pr")

    result = _invoke(
        {
            "base_ref": "origin/main",
            "repo_path": str(repo.path),
            "pr_title": "PR",
            "pr_body": "body",
            **TARGET,
        }
    )

    assert result["change"] == {
        "intent": [],
        "code": ["src/added.py", "src/app.py", "src/renamed.py"],
        "ignored": ["src/gone.py"],
    }
    assert "diff" not in result


def test_pr_with_code_and_intent_reaches_publish(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    repo = git_repo("pr")
    repo.write("src/app.py", "print('before')\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)

    repo.git("switch", "-c", "pr")
    repo.write("src/app.py", "print('after')\n")
    repo.write(".scratch/change-collection/spec.md", "# Spec\n")
    repo.write("docs/adr/0001-decision.md", "# ADR\n")
    repo.commit("pr")

    result = _invoke(
        {
            "base_ref": "origin/main",
            "repo_path": str(repo.path),
            "pr_title": "PR",
            "pr_body": "",
            **TARGET,
        }
    )

    assert result["change"] == {
        "intent": [".scratch/change-collection/spec.md", "docs/adr/0001-decision.md"],
        "code": ["src/app.py"],
        "ignored": [],
    }


def _invoke(graph_input: dict[str, Any]) -> dict[str, Any]:
    """Runs the graph to the end. The nodes with a model are async, hence ainvoke."""
    return asyncio.run(build_graph().ainvoke(graph_input))


def _updates(graph_input: dict[str, Any]) -> list[dict[str, Any]]:
    """Every node update in order, one chunk per node execution."""

    async def collect() -> list[dict[str, Any]]:
        graph = build_graph()
        return [chunk async for chunk in graph.astream(graph_input, stream_mode="updates")]

    return asyncio.run(collect())


def _executed_nodes(graph_input: dict[str, Any]) -> list[str]:
    """Names of the nodes that ran, in order (one entry per node execution)."""
    return [name for chunk in _updates(graph_input) for name in chunk]


def test_pr_with_only_docs_and_lockfile_ends_in_nothing_to_review(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = git_repo("pr")
    repo.write("README.md", "# readme\n")
    repo.write("uv.lock", "version = 1\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)

    repo.git("switch", "-c", "pr")
    repo.write("README.md", "# readme, edited\n")
    repo.write("uv.lock", "version = 2\n")
    repo.write("docs/agents/issue-tracker.md", "# tracker\n")
    repo.write(".scratch/feature/spec.md", "# Spec\n")
    repo.commit("pr")

    result = _invoke(
        {
            "base_ref": "origin/main",
            "repo_path": str(repo.path),
            "pr_title": "PR",
            "pr_body": "",
            **TARGET,
        }
    )

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "collect_input: hello world"
    assert len(lines) == 2
    assert lines[1].startswith("nothing_to_review:")
    assert "3 ignored" in lines[1]
    assert "1 intent" in lines[1]
    assert "summary" not in result
    assert result["change"] == {
        "intent": [".scratch/feature/spec.md"],
        "code": [],
        "ignored": ["README.md", "docs/agents/issue-tracker.md", "uv.lock"],
    }


def test_command_and_edges_do_not_both_route(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    repo = git_repo("pr")
    repo.write("README.md", "# readme\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)
    repo.git("switch", "-c", "pr")
    repo.write("README.md", "# readme, edited\n")
    repo.commit("pr")

    executed = _executed_nodes(
        {
            "base_ref": "origin/main",
            "repo_path": str(repo.path),
            "pr_title": "PR",
            "pr_body": "",
            **TARGET,
        }
    )

    assert executed == ["collect_input", "nothing_to_review"]


def test_pr_with_code_skips_nothing_to_review(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    repo = git_repo("pr")
    repo.write("src/app.py", "print('before')\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)
    repo.git("switch", "-c", "pr")
    repo.write("src/app.py", "print('after')\n")
    repo.commit("pr")

    executed = _executed_nodes(
        {
            "base_ref": "origin/main",
            "repo_path": str(repo.path),
            "pr_title": "PR",
            "pr_body": "",
            **TARGET,
        }
    )

    assert "nothing_to_review" not in executed


def test_transient_git_failure_is_retried(
    monkeypatch: pytest.MonkeyPatch, fake_github: FakeGitHub
) -> None:
    change: Change = {"intent": [], "code": ["src/app.py"], "ignored": []}
    calls = 0

    def flaky_collect_change(base_ref: str, repo: Path) -> Change:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise subprocess.CalledProcessError(
                128,
                ["git", "diff"],
                stderr="fatal: Unable to create '.git/index.lock': File exists.",
            )
        return change

    monkeypatch.setattr(collect_input_module, "collect_change", flaky_collect_change)
    monkeypatch.setattr(review_code_module, "file_diff", lambda *args: "")
    fast_retry = graph_module.COLLECT_INPUT_RETRY._replace(initial_interval=0, jitter=False)
    monkeypatch.setattr(graph_module, "COLLECT_INPUT_RETRY", fast_retry)

    result = _invoke(
        {"base_ref": "origin/main", "repo_path": ".", "pr_title": "PR", "pr_body": "", **TARGET}
    )

    assert calls == 2
    assert result["change"] == change


def test_permanent_git_failure_is_not_retried(
    git_repo: Callable[[str], GitRepo],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = git_repo("pr")
    repo.write("src/app.py", "print('hi')\n")
    repo.commit("base")
    calls = 0

    def counting_collect_change(base_ref: str, path: Path) -> Change:
        nonlocal calls
        calls += 1
        return collect_change(base_ref, path)

    monkeypatch.setattr(collect_input_module, "collect_change", counting_collect_change)

    with pytest.raises(subprocess.CalledProcessError):
        _invoke(
            {
                "base_ref": "origin/does-not-exist",
                "repo_path": str(repo.path),
                "pr_title": "PR",
                "pr_body": "",
            }
        )

    assert calls == 1


def test_missing_base_ref_fails_before_touching_git(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def spy_collect_change(base_ref: str, repo: Path) -> Change:
        nonlocal calls
        calls += 1
        return {"intent": [], "code": [], "ignored": []}

    monkeypatch.setattr(collect_input_module, "collect_change", spy_collect_change)

    with pytest.raises(ValueError, match="base_ref"):
        _invoke({"repo_path": ".", "pr_title": "PR", "pr_body": "", **TARGET})

    assert calls == 0


def test_git_timeout_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def hanging_collect_change(base_ref: str, repo: Path) -> Change:
        nonlocal calls
        calls += 1
        raise subprocess.TimeoutExpired(cmd=["git", "diff"], timeout=30)

    monkeypatch.setattr(collect_input_module, "collect_change", hanging_collect_change)
    fast_retry = graph_module.COLLECT_INPUT_RETRY._replace(initial_interval=0, jitter=False)
    monkeypatch.setattr(graph_module, "COLLECT_INPUT_RETRY", fast_retry)

    with pytest.raises(subprocess.TimeoutExpired):
        _invoke(
            {"base_ref": "origin/main", "repo_path": ".", "pr_title": "PR", "pr_body": "", **TARGET}
        )

    assert calls == 1


def _pr_input(repo: GitRepo, **overrides: object) -> dict[str, Any]:
    return {
        "base_ref": "origin/main",
        "repo_path": str(repo.path),
        "pr_title": "PR",
        "pr_body": "",
        **TARGET,
        **overrides,
    }


def _docs_only_pr(git_repo: Callable[[str], GitRepo]) -> GitRepo:
    repo = git_repo("pr")
    repo.write("README.md", "# readme\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)
    repo.git("switch", "-c", "pr")
    repo.write("README.md", "# readme, edited\n")
    repo.write("uv.lock", "version = 2\n")
    repo.write(".scratch/feature/spec.md", "# Spec\n")
    repo.commit("pr")
    return repo


def _code_pr(git_repo: Callable[[str], GitRepo]) -> GitRepo:
    repo = git_repo("pr")
    repo.write("src/app.py", "print('before')\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)
    repo.git("switch", "-c", "pr")
    repo.write("src/app.py", "print('after')\n")
    repo.write("src/added.py", "print('added')\n")
    repo.commit("pr")
    return repo


def _instant_github_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    fast = graph_module.GITHUB_RETRY._replace(initial_interval=0, jitter=False)
    monkeypatch.setattr(graph_module, "GITHUB_RETRY", fast)


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.github.com", code, "boom", Message(), None)


def test_pr_without_code_leaves_one_status_comment(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    repo = _docs_only_pr(git_repo)

    _invoke(_pr_input(repo))

    assert len(fake_github.comments) == 1
    body = fake_github.comments[0]["body"]
    assert "brak kodu do sprawdzenia" in body
    assert "pominięte pliki: 2" in body
    assert "pliki Intent: 1" in body
    assert "0123456" in body
    assert fake_github.requests[-1][0] == "POST"


def test_pr_with_code_leaves_one_comment_with_summary(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    repo = _code_pr(git_repo)

    _invoke(_pr_input(repo))

    assert len(fake_github.comments) == 1
    body = fake_github.comments[0]["body"]
    assert "sprawdzono plików: 2, uwagi: 2" in body
    assert "stub summary" in body


def test_second_run_on_the_same_pr_edits_the_comment(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    repo = _code_pr(git_repo)

    _invoke(_pr_input(repo, head_sha="1111111aaaaaaa"))
    _invoke(_pr_input(repo, head_sha="2222222bbbbbbb"))

    assert len(fake_github.comments) == 1
    assert "2222222" in fake_github.comments[0]["body"]
    assert "1111111" not in fake_github.comments[0]["body"]
    assert [method for method, _ in fake_github.requests].count("PATCH") == 1


def test_run_after_a_docs_only_push_overwrites_the_code_review_status(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    _invoke(_pr_input(_code_pr(git_repo)))
    docs_repo = _docs_only_pr(lambda name: git_repo(f"{name}-docs"))

    _invoke(_pr_input(docs_repo))

    assert len(fake_github.comments) == 1
    assert "brak kodu do sprawdzenia" in fake_github.comments[0]["body"]


def test_transient_github_error_is_retried(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _instant_github_retry(monkeypatch)
    fake_github.fail_next = _http_error(503)

    _invoke(_pr_input(_code_pr(git_repo)))

    assert len(fake_github.comments) == 1


def test_retry_after_a_lost_response_does_not_duplicate_the_comment(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _instant_github_retry(monkeypatch)
    fake_github.fail_after_write = TimeoutError("timed out")

    _invoke(_pr_input(_code_pr(git_repo)))

    assert len(fake_github.comments) == 1
    assert [method for method, _ in fake_github.requests].count("PATCH") == 1


@pytest.mark.parametrize("code", [401, 403, 404])
def test_permanent_github_error_fails_the_run_without_retry(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
    code: int,
) -> None:
    _instant_github_retry(monkeypatch)
    fake_github.fail_next = _http_error(code)

    with pytest.raises(urllib.error.HTTPError):
        _invoke(_pr_input(_docs_only_pr(git_repo)))

    assert len(fake_github.requests) == 1
    assert fake_github.comments == []


def test_missing_token_fails_the_run(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN")

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        _invoke(_pr_input(_code_pr(git_repo)))

    assert fake_github.requests == []


def test_missing_target_fails_the_run(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    repo = _docs_only_pr(git_repo)
    graph_input = _pr_input(repo)
    del graph_input["repo"]

    with pytest.raises(ValueError, match="repo"):
        _invoke(graph_input)

    assert fake_github.requests == []


def test_dry_run_prints_the_comment_and_sends_nothing(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _docs_only_pr(git_repo)

    _invoke({"base_ref": "origin/main", "repo_path": str(repo.path), "dry_run": True})

    assert "brak kodu do sprawdzenia" in capsys.readouterr().out
    assert fake_github.requests == []


def test_token_never_reaches_the_update_stream(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_secret_value")
    repo = _code_pr(git_repo)

    chunks = _updates(_pr_input(repo))

    assert "ghs_secret_value" not in repr(chunks)
    assert fake_github.tokens == {"ghs_secret_value"}


def _pr_with_files(
    git_repo: Callable[[str], GitRepo], *, code: list[str], intent: list[str] | None = None
) -> GitRepo:
    repo = git_repo("pr")
    repo.write("README.md", "# readme\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)
    repo.git("switch", "-c", "pr")
    for path in [*code, *(intent or [])]:
        repo.write(path, f"# {path}\n")
    repo.commit("pr")
    return repo


def _count(executed: list[str], node: str) -> int:
    return executed.count(node)


@pytest.mark.parametrize("files", [1, 3])
def test_review_code_runs_once_per_code_file(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub, files: int
) -> None:
    code = [f"src/m{n}.py" for n in range(files)]
    repo = _pr_with_files(git_repo, code=code)

    executed = _executed_nodes(_pr_input(repo))

    assert _count(executed, "review_code") == files
    assert _count(executed, "review_intent") == 0
    assert _count(executed, "validate_findings") == 1


def test_review_intent_runs_once_and_only_with_intent_files(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    with_intent = _pr_with_files(
        git_repo,
        code=["src/a.py", "src/b.py"],
        intent=[".scratch/feature/spec.md", "docs/adr/0001-x.md"],
    )

    executed = _executed_nodes(_pr_input(with_intent))

    assert _count(executed, "review_intent") == 1
    assert _count(executed, "review_code") == 2


def test_validate_findings_waits_for_every_reviewer(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    repo = _pr_with_files(
        git_repo, code=["src/a.py", "src/b.py"], intent=[".scratch/feature/spec.md"]
    )

    updates = _updates(_pr_input(repo))

    names = [name for chunk in updates for name in chunk]
    assert _count(names, "validate_findings") == 1
    validated = next(c["validate_findings"] for c in updates if "validate_findings" in c)
    assert {f["source"] for f in validated["validated"]} == {"code", "spec"}
    assert len(validated["validated"]) == 3
    last_reviewer = max(i for i, n in enumerate(names) if n.startswith("review_"))
    assert names.index("validate_findings") > last_reviewer


def test_reducer_keeps_every_reviewers_remarks(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    repo = _pr_with_files(
        git_repo, code=["src/a.py", "src/b.py"], intent=[".scratch/feature/spec.md"]
    )

    result = _invoke(_pr_input(repo))

    assert {f["id"] for f in result["candidates"]} == {
        "code:src/a.py:1:1",
        "code:src/b.py:1:1",
        "spec:1",
    }
    assert len(result["verdicts"]) == 3
    assert len(result["findings"]) == 3
    assert result["summary"] == "stub summary"


def test_each_finding_is_verified_once_before_the_judge(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub
) -> None:
    repo = _pr_with_files(git_repo, code=["src/a.py", "src/b.py", "src/c.py"])

    executed = _executed_nodes(_pr_input(repo))

    assert _count(executed, "verify_finding") == 3
    assert _count(executed, "judge_findings") == 1
    assert executed[-2:] == ["judge_findings", "publish"]


def test_no_findings_goes_straight_to_publish(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def silent_review_code(payload: dict[str, str]) -> dict[str, list[Any]]:
        return {"candidates": []}

    monkeypatch.setattr(graph_module, "review_code", silent_review_code)
    repo = _pr_with_files(git_repo, code=["src/a.py", "src/b.py"])

    executed = _executed_nodes(_pr_input(repo))

    assert _count(executed, "verify_finding") == 0
    assert _count(executed, "judge_findings") == 0
    assert executed[-2:] == ["validate_findings", "publish"]
    assert "brak uwag" in fake_github.comments[0]["body"]


def test_verification_is_capped_and_the_rest_goes_on_unverified(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(validate_findings_module, "MAX_VERIFICATIONS", 2)
    repo = _pr_with_files(git_repo, code=[f"src/m{n}.py" for n in range(5)])

    executed = _executed_nodes(_pr_input(repo))
    result = _invoke(_pr_input(repo))

    assert _count(executed, "verify_finding") == 2
    assert len(result["verdicts"]) == 2
    assert len(result["findings"]) == 5


def test_most_severe_findings_are_verified_first(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def graded_review_code(payload: dict[str, str]) -> dict[str, list[Any]]:
        severity = "high" if payload["path"] == "src/m3.py" else "low"
        finding = {"id": payload["path"], "source": "code", "severity": severity, "message": "m"}
        return {"candidates": [finding]}

    monkeypatch.setattr(graph_module, "review_code", graded_review_code)
    monkeypatch.setattr(validate_findings_module, "MAX_VERIFICATIONS", 1)
    repo = _pr_with_files(git_repo, code=[f"src/m{n}.py" for n in range(5)])

    result = _invoke(_pr_input(repo))

    assert [v["finding_id"] for v in result["verdicts"]] == ["src/m3.py"]


def test_concurrency_is_bounded_by_the_constant(
    git_repo: Callable[[str], GitRepo],
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = peak = 0

    async def slow_review_code(payload: dict[str, str]) -> dict[str, list[Any]]:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1
        return {"candidates": []}

    monkeypatch.setattr(graph_module, "MAX_CONCURRENCY", 2)
    monkeypatch.setattr(graph_module, "review_code", slow_review_code)
    repo = _pr_with_files(git_repo, code=[f"src/m{n}.py" for n in range(6)])

    _invoke(_pr_input(repo))

    assert peak == 2


def _instant_agent_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    fast = graph_module.AGENT_RETRY._replace(initial_interval=0, jitter=False)
    monkeypatch.setattr(graph_module, "AGENT_RETRY", fast)


def _api_error(status: int | None, reason: str = "api_error") -> ResultError:
    return ResultError(
        "API Error",
        data={"subtype": "success", "api_error_status": status, "terminal_reason": reason},
        exit_code=1,
    )


def test_review_code_turns_the_answer_into_findings_and_reads_the_diff(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub, fake_agent: FakeAgent
) -> None:
    repo = _pr_with_files(git_repo, code=["src/a.py"])
    fake_agent.respond = lambda call: {
        "findings": [
            {
                "severity": "high",
                "message": "wynik jest ignorowany",
                "line": 1,
                "evidence": "# src/a.py",
                "suggestion": "sprawdź wynik",
            }
        ]
    }

    result = _invoke(_pr_input(repo))

    assert result["candidates"] == [
        {
            "id": "code:src/a.py:1:1",
            "source": "code",
            "severity": "high",
            "message": "wynik jest ignorowany",
            "file": "src/a.py",
            "line": 1,
            "evidence": "# src/a.py",
            "suggestion": "sprawdź wynik",
        }
    ]
    (call,) = fake_agent.calls
    assert call["model"] == agent.REVIEW_MODEL
    assert call["cwd"] == str(repo.path)
    assert "+# src/a.py" in call["prompt"]  # the file's diff is part of the prompt


def test_review_code_does_not_trust_the_model_for_source_or_id(
    git_repo: Callable[[str], GitRepo], fake_github: FakeGitHub, fake_agent: FakeAgent
) -> None:
    repo = _pr_with_files(git_repo, code=["src/a.py"])
    fake_agent.respond = lambda call: {
        "findings": [
            {
                "severity": "low",
                "message": "m",
                "line": 1,
                "evidence": "e",
                "source": "spec",
                "id": "x",
            }
        ]
    }

    result = _invoke(_pr_input(repo))

    (finding,) = result["candidates"]
    assert (finding["source"], finding["id"]) == ("code", "code:src/a.py:1:1")


def test_transient_agent_failure_is_retried_once(
    git_repo: Callable[[str], GitRepo],
    monkeypatch: pytest.MonkeyPatch,
    fake_github: FakeGitHub,
    fake_agent: FakeAgent,
) -> None:
    _instant_agent_retry(monkeypatch)
    repo = _pr_with_files(git_repo, code=["src/a.py"])
    attempts = iter([_api_error(529), {"findings": []}])
    fake_agent.respond = lambda call: next(attempts)

    result = _invoke(_pr_input(repo))

    assert len(fake_agent.calls) == 2
    assert result["candidates"] == []


def test_permanent_agent_failure_is_not_retried(
    git_repo: Callable[[str], GitRepo],
    monkeypatch: pytest.MonkeyPatch,
    fake_github: FakeGitHub,
    fake_agent: FakeAgent,
) -> None:
    _instant_agent_retry(monkeypatch)
    repo = _pr_with_files(git_repo, code=["src/a.py"])
    fake_agent.respond = lambda call: _api_error(401)

    with pytest.raises(ResultError):
        _invoke(_pr_input(repo))

    assert len(fake_agent.calls) == 1


def test_retrying_one_file_does_not_rerun_the_others(
    git_repo: Callable[[str], GitRepo],
    monkeypatch: pytest.MonkeyPatch,
    fake_github: FakeGitHub,
    fake_agent: FakeAgent,
) -> None:
    _instant_agent_retry(monkeypatch)
    repo = _pr_with_files(git_repo, code=["src/a.py", "src/b.py", "src/c.py"])
    failed_once = False

    def respond(call: dict[str, Any]) -> dict[str, Any] | Exception:
        nonlocal failed_once
        if call["prompt"].startswith("File: src/b.py") and not failed_once:
            failed_once = True
            return _api_error(429)
        return {"findings": []}

    fake_agent.respond = respond

    _invoke(_pr_input(repo))

    assert [len(fake_agent.calls_for(p)) for p in ("src/a.py", "src/b.py", "src/c.py")] == [1, 2, 1]


def test_agent_run_that_hangs_hits_the_node_timeout_and_is_retried(
    git_repo: Callable[[str], GitRepo],
    monkeypatch: pytest.MonkeyPatch,
    fake_github: FakeGitHub,
    fake_agent: FakeAgent,
) -> None:
    _instant_agent_retry(monkeypatch)
    monkeypatch.setattr(graph_module, "NODE_TIMEOUT_SECONDS", 0.05)
    repo = _pr_with_files(git_repo, code=["src/a.py"])
    calls = 0

    async def sometimes_hangs(**kwargs: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 1:
            await asyncio.sleep(5)
        return {"findings": []}

    monkeypatch.setattr(agent, "run_agent", sometimes_hangs)

    _invoke(_pr_input(repo))

    assert calls == 2
