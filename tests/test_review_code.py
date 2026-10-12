import asyncio
import os
from collections.abc import Callable

import pytest
from gitrepo import GitRepo

from gha_assistant import agent
from gha_assistant.nodes import review_code as review_code_module
from gha_assistant.nodes.review_code import build_prompt, review_code

# The fixtures replace both names on the module; this is the real function bound at import.
real_run_agent = agent.run_agent


def test_prompt_marks_the_diff_as_data_and_names_the_file() -> None:
    prompt = build_prompt("src/a.py", "+x = 1\n")

    assert prompt.startswith("File: src/a.py\n")
    assert '<diff path="src/a.py">\n+x = 1\n' in prompt


def test_huge_diff_is_truncated_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(review_code_module, "MAX_DIFF_CHARS", 10)

    prompt = build_prompt("src/a.py", "+" + "x" * 100)

    assert "x" * 100 not in prompt
    assert "diff truncated" in prompt


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")
def test_real_model_reviews_a_file_with_an_obvious_bug(
    monkeypatch: pytest.MonkeyPatch, git_repo: Callable[[str], GitRepo]
) -> None:
    from claude_agent_sdk import query as real_query

    monkeypatch.setattr(agent, "query", real_query)
    monkeypatch.setattr(agent, "run_agent", real_run_agent)
    repo = git_repo("pr")
    repo.write("src/calc.py", "def average(values):\n    return sum(values) / len(values)\n")
    base = repo.commit("base")
    repo.git("update-ref", "refs/remotes/origin/main", base)
    repo.git("switch", "-c", "pr")
    repo.write(
        "src/calc.py",
        "def average(values):\n"
        "    total = 0\n"
        "    for value in values:\n"
        "        total += value\n"
        "    return total / len(values) + 1\n"
        "\n"
        "\n"
        "def first(items):\n"
        "    return items[len(items)]\n",
    )
    repo.commit("pr")

    payload = {"path": "src/calc.py", "base_ref": "origin/main", "repo_path": str(repo.path)}
    result = asyncio.run(review_code(payload))

    findings = result["candidates"]
    assert findings, "the model found nothing in an obviously broken file"
    for finding in findings:
        assert finding["source"] == "code"
        assert finding["file"] == "src/calc.py"
        assert isinstance(finding["line"], int)
        assert finding["severity"] in ("low", "medium", "high")
        assert finding["id"].startswith("code:src/calc.py:")
