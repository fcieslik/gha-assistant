import pytest

from gha_assistant.graph import build_graph


def test_graph_runs_nodes_in_order(capsys: pytest.CaptureFixture[str]) -> None:
    result = build_graph().invoke({})

    assert capsys.readouterr().out.splitlines() == [
        "collect_input: hello world",
        "run_agent: hello world",
        "publish: hello world",
    ]
    assert result == {"diff": "stub diff", "summary": "stub summary"}
