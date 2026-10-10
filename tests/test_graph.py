from collections.abc import Callable

import pytest
from gitrepo import GitRepo

from gha_assistant.graph import build_graph


def test_graph_runs_nodes_in_order(
    git_repo: Callable[[str], GitRepo],
    capsys: pytest.CaptureFixture[str],
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

    result = build_graph().invoke(
        {
            "base_ref": "origin/main",
            "repo_path": str(repo.path),
            "pr_title": "PR",
            "pr_body": "body",
        }
    )

    assert capsys.readouterr().out.splitlines() == [
        "collect_input: hello world",
        "run_agent: hello world",
        "publish: hello world",
    ]
    assert result["change"] == {
        "intent": [],
        "code": ["src/added.py", "src/app.py", "src/renamed.py"],
        "ignored": ["src/gone.py"],
    }
    assert "diff" not in result


def test_pr_with_code_and_intent_reaches_publish(
    git_repo: Callable[[str], GitRepo],
    capsys: pytest.CaptureFixture[str],
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

    result = build_graph().invoke(
        {"base_ref": "origin/main", "repo_path": str(repo.path), "pr_title": "PR", "pr_body": ""}
    )

    assert capsys.readouterr().out.splitlines() == [
        "collect_input: hello world",
        "run_agent: hello world",
        "publish: hello world",
    ]
    assert result["change"] == {
        "intent": [".scratch/change-collection/spec.md", "docs/adr/0001-decision.md"],
        "code": ["src/app.py"],
        "ignored": [],
    }


def test_pr_with_only_docs_and_lockfile_ends_after_collect_input(
    git_repo: Callable[[str], GitRepo],
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
    repo.commit("pr")

    result = build_graph().invoke(
        {"base_ref": "origin/main", "repo_path": str(repo.path), "pr_title": "PR", "pr_body": ""}
    )

    assert capsys.readouterr().out.splitlines() == ["collect_input: hello world"]
    assert "summary" not in result
    assert result["change"] == {
        "intent": [],
        "code": [],
        "ignored": ["README.md", "docs/agents/issue-tracker.md", "uv.lock"],
    }
