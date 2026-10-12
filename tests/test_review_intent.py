import asyncio
import os
from collections.abc import Callable

import pytest
from gitrepo import GitRepo

from gha_assistant import agent
from gha_assistant.nodes import review_intent as review_intent_module
from gha_assistant.nodes.review_intent import build_prompt, make_review_intent, to_findings

# The fixtures replace this name on the module; this is the real function bound at import.
real_run_agent = agent.run_agent


def test_prompt_lists_the_files_and_marks_each_diff_as_data() -> None:
    prompt = build_prompt(
        [".scratch/x/spec.md"],
        ["src/a.py", "src/b.py"],
        {"src/a.py": "+a\n", "src/b.py": "+b\n"},
        "T",
        "B",
    )

    assert prompt.startswith("<intent_files>\n.scratch/x/spec.md\n</intent_files>")
    assert "<changed_files>\nsrc/a.py\nsrc/b.py\n</changed_files>" in prompt
    assert '<diff path="src/a.py">\n+a\n\n</diff>' in prompt
    assert '<diff path="src/b.py">\n+b\n\n</diff>' in prompt
    assert prompt.endswith("<pr>\nTitle: T\n\nB\n</pr>")


def test_diffs_share_one_budget_and_say_when_they_are_cut(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(review_intent_module, "MAX_DIFF_CHARS", 10)

    prompt = build_prompt([], ["a", "b"], {"a": "+" + "x" * 100, "b": "+" + "y" * 100}, "", "")

    assert "x" * 10 not in prompt
    assert "y" not in prompt
    assert prompt.count("diff truncated") == 2


def test_findings_get_source_and_ids_from_code_and_keep_only_what_the_model_gave() -> None:
    findings = to_findings(
        {
            "findings": [
                {"severity": "low", "message": "m", "spec_ref": "s.md: x"},
                {
                    "severity": "high",
                    "message": "n",
                    "spec_ref": "s.md: y",
                    "file": "a.py",
                    "line": 3,
                },
            ]
        }
    )

    assert findings == [
        {
            "id": "spec:1",
            "source": "spec",
            "severity": "low",
            "message": "m",
            "spec_ref": "s.md: x",
        },
        {
            "id": "spec:2",
            "source": "spec",
            "severity": "high",
            "message": "n",
            "spec_ref": "s.md: y",
            "file": "a.py",
            "line": 3,
        },
    ]


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")
def test_real_model_finds_a_requirement_the_change_does_not_meet(
    monkeypatch: pytest.MonkeyPatch, git_repo: Callable[[str], GitRepo]
) -> None:
    from claude_agent_sdk import query as real_query
    from langgraph.types import RetryPolicy

    monkeypatch.setattr(agent, "query", real_query)
    monkeypatch.setattr(agent, "run_agent", real_run_agent)
    repo = git_repo("pr")
    repo.write("src/stats.py", "def mean(values):\n    return sum(values) / len(values)\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)
    repo.git("switch", "-c", "pr")
    repo.write(
        ".scratch/stats/issues/01-median.md",
        "# 01: median\n\n"
        "- [ ] `stats.median(values)` returns the middle value of a sorted list\n"
        "- [ ] `stats.median([])` returns 0.0\n",
    )
    repo.write(
        "src/stats.py",
        "def mean(values):\n    return sum(values) / len(values)\n\n\n"
        "def median(values):\n"
        "    ordered = sorted(values)\n"
        "    return ordered[len(ordered) // 2]\n",
    )
    repo.commit("pr")
    state = {
        "base_ref": "origin/main",
        "repo_path": str(repo.path),
        "pr_title": "Add median",
        "pr_body": "",
        "change": {
            "intent": [".scratch/stats/issues/01-median.md"],
            "code": ["src/stats.py"],
            "ignored": [],
        },
    }

    node = make_review_intent(RetryPolicy(max_attempts=1), 300)
    result = asyncio.run(node(state))  # type: ignore[arg-type]

    assert result["warnings"] == []
    findings = result["candidates"]
    assert findings, "the model missed the unmet `median([])` criterion"
    for finding in findings:
        assert finding["source"] == "spec"
        assert finding["spec_ref"]
        assert finding["id"].startswith("spec:")
