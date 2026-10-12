import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ProcessError,
    ResultError,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)
from claude_agent_sdk import query as real_query
from langgraph.errors import NodeTimeoutError

from gha_assistant import agent
from gha_assistant.agent import (
    FALLBACK_MODEL,
    READ_ONLY_TOOLS,
    REVIEW_MODEL,
    VERIFY_MODEL,
    InvalidAgentOutput,
    is_transient_agent_error,
)

# `run_agent` as imported here is the real one: the autouse fake only replaces the
# attribute on the module, not this name.
run_agent = agent.run_agent
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


def _result(**overrides: Any) -> ResultMessage:
    fields: dict[str, Any] = {
        "subtype": "success",
        "duration_ms": 1,
        "duration_api_ms": 1,
        "is_error": False,
        "num_turns": 1,
        "session_id": "s",
        "structured_output": {"ok": True},
    }
    return ResultMessage(**{**fields, **overrides})


def _result_error(
    status: int | None = None, *, subtype: str = "success", reason: str | None = "api_error"
) -> ResultError:
    data = {"subtype": subtype, "api_error_status": status, "terminal_reason": reason}
    return ResultError("run failed", data=data, exit_code=1)


class _FakeQuery:
    """Replaces the SDK's `query`: yields `messages`, then raises `then_raise`."""

    def __init__(self, *messages: object, then_raise: Exception | None = None) -> None:
        self.messages = messages
        self.then_raise = then_raise
        self.options: ClaudeAgentOptions | None = None
        self.prompt: str | None = None

    def __call__(self, *, prompt: str, options: ClaudeAgentOptions) -> AsyncIterator[object]:
        self.prompt, self.options = prompt, options
        return self._stream()

    async def _stream(self) -> AsyncIterator[object]:
        for message in self.messages:
            yield message
        if self.then_raise is not None:
            raise self.then_raise


def _run(fake: _FakeQuery, monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> dict[str, Any]:
    monkeypatch.setattr(agent, "query", fake)
    params: dict[str, Any] = {
        "model": REVIEW_MODEL,
        "system_prompt": "do the task",
        "prompt": "go",
        "output_schema": SCHEMA,
        **kwargs,
    }
    return asyncio.run(run_agent(**params))


def _options_for(monkeypatch: pytest.MonkeyPatch, **kwargs: Any) -> ClaudeAgentOptions:
    fake = _FakeQuery(_result())
    _run(fake, monkeypatch, **kwargs)
    assert fake.options is not None
    return fake.options


def test_run_agent_returns_the_structured_output(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeQuery(_result(structured_output={"ok": True}))

    assert _run(fake, monkeypatch) == {"ok": True}
    assert fake.prompt == "go"


def test_options_allow_reading_only_and_ignore_the_reviewed_repos_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    options = _options_for(monkeypatch)

    assert options.tools == list(READ_ONLY_TOOLS) == ["Read", "Glob", "Grep"]
    assert options.allowed_tools == options.tools
    assert options.permission_mode == "dontAsk"  # anything else is refused, not asked
    assert options.setting_sources == []  # no CLAUDE.md or .claude/ from the PR
    assert options.max_turns == 30
    assert options.max_budget_usd == 0.5
    assert options.effort == "medium"
    assert options.output_format == {"type": "json_schema", "schema": SCHEMA}


def test_a_node_can_raise_the_turn_and_budget_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    options = _options_for(
        monkeypatch,
        max_turns=agent.REVIEW_INTENT_MAX_TURNS,
        max_budget_usd=agent.REVIEW_INTENT_MAX_BUDGET_USD,
    )

    assert options.max_turns == 100
    assert options.max_budget_usd == 0.75


def test_an_empty_tool_list_means_no_tools_at_all(monkeypatch: pytest.MonkeyPatch) -> None:
    options = _options_for(monkeypatch, tools=[])

    # An empty list must reach the CLI as "no tools", not fall back to the default set.
    assert options.tools == []
    assert options.allowed_tools == []


def test_fallback_model_is_left_out_when_it_equals_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _options_for(monkeypatch, model=REVIEW_MODEL).fallback_model == FALLBACK_MODEL
    assert _options_for(monkeypatch, model=VERIFY_MODEL).fallback_model is None


def test_the_cli_retry_budget_is_set_explicitly(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _options_for(monkeypatch).env["CLAUDE_CODE_MAX_RETRIES"] == agent.CLI_MAX_RETRIES


def test_rules_file_comes_before_the_task_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    system_prompt = _options_for(monkeypatch, system_prompt="THE TASK").system_prompt
    rules = (agent.PROMPTS_DIR / "rules.md").read_text().strip()

    assert isinstance(system_prompt, str)
    assert system_prompt == f"{rules}\n\nTHE TASK"


def test_prompts_live_in_one_folder_and_none_is_a_claude_md() -> None:
    # Developer sessions in this repo would load a CLAUDE.md found next to the sources.
    names = {path.name for path in agent.PROMPTS_DIR.iterdir()}

    assert {"rules.md", "review_code.md"} <= names
    assert "CLAUDE.md" not in names
    assert not list(Path(agent.__file__).parent.rglob("CLAUDE.md"))
    assert all(agent.load_prompt(path.stem) for path in agent.PROMPTS_DIR.glob("*.md"))


def test_progress_log_lists_tool_calls_and_the_result_but_not_model_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _FakeQuery(
        AssistantMessage(
            content=[
                TextBlock(text="the token is ghs_secret"),
                ToolUseBlock(id="1", name="Read", input={"file_path": "src/app.py"}),
                ToolUseBlock(id="2", name="Grep", input={"pattern": "def main"}),
            ],
            model="m",
        ),
        _result(total_cost_usd=0.0123, num_turns=3, duration_ms=4200),
    )

    _run(fake, monkeypatch, label="review_code src/a.py")

    captured = capsys.readouterr()
    assert captured.err.splitlines() == [
        "[review_code src/a.py] Read src/app.py",
        "[review_code src/a.py] Grep def main",
        "[review_code src/a.py] success: turns=3 cost=$0.0123 duration=4.2s",
    ]
    assert "ghs_secret" not in captured.out + captured.err


def test_progress_log_cannot_be_used_to_inject_workflow_commands(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    hostile = "x\n::add-mask::value\r\n::stop-commands::token\x1b[2K" + "y" * 500
    fake = _FakeQuery(
        AssistantMessage(
            content=[ToolUseBlock(id="1", name="Read", input={"file_path": hostile})],
            model="m",
        ),
        _result(),
    )

    _run(fake, monkeypatch, label="review_code ::stop-commands::\nsrc/a.py")

    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 2  # the hostile input did not add lines
    assert all(line.startswith("[review_code ") for line in lines)
    assert all(len(line) < 250 for line in lines)


def test_progress_log_reports_a_failed_run_before_the_error_is_raised(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _FakeQuery(
        _result(subtype="error_max_turns", is_error=True, structured_output=None),
        then_raise=_result_error(None, subtype="error_max_turns", reason="max_turns"),
    )

    with pytest.raises(ResultError):
        _run(fake, monkeypatch, label="verify_finding f1")

    assert "[verify_finding f1] error_max_turns (error)" in capsys.readouterr().err


def test_missing_structured_output_is_invalid_agent_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeQuery(_result(structured_output=None))

    with pytest.raises(InvalidAgentOutput):
        _run(fake, monkeypatch)


@pytest.mark.parametrize(
    ("subtype", "transient"),
    [
        ("error_max_turns", False),
        ("error_max_budget_usd", False),
        ("error_max_structured_output_retries", True),
        ("error_during_execution", True),
    ],
)
def test_error_result_without_a_raised_error_is_classified_by_subtype(
    monkeypatch: pytest.MonkeyPatch, subtype: str, transient: bool
) -> None:
    # An is_error result that the SDK did not follow with ResultError.
    fake = _FakeQuery(_result(subtype=subtype, is_error=True, structured_output=None))

    with pytest.raises(ResultError) as caught:
        _run(fake, monkeypatch)

    assert caught.value.subtype == subtype
    assert is_transient_agent_error(caught.value) is transient


def test_failed_run_surfaces_the_original_error_not_invalid_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The SDK yields the error result first and raises afterwards; stopping at the
    # result would turn a 401 into a retried InvalidAgentOutput.
    fake = _FakeQuery(
        _result(is_error=True, structured_output=None, api_error_status=401),
        then_raise=_result_error(401),
    )

    with pytest.raises(ResultError) as caught:
        _run(fake, monkeypatch)

    assert caught.value.api_error_status == 401


@pytest.mark.parametrize(
    "exc",
    [
        # Measured in the spike: a refused connection arrives as a ResultError without status.
        _result_error(None, reason="api_error"),
        _result_error(None, subtype="error_max_structured_output_retries", reason=None),
        _result_error(None, subtype="error_during_execution", reason=None),
        _result_error(429),
        _result_error(500),
        _result_error(503),
        _result_error(529),
        NodeTimeoutError("review_code", 120.0, kind="run", run_timeout=120.0),
        InvalidAgentOutput("no structured output"),
        CLIConnectionError("lost the CLI"),
        ProcessError("exit 1", exit_code=1),
    ],
    ids=lambda exc: f"{type(exc).__name__}-{getattr(exc, 'api_error_status', '')}",
)
def test_transient_agent_errors(exc: Exception) -> None:
    assert is_transient_agent_error(exc)


@pytest.mark.parametrize(
    "exc",
    [
        # Measured in the spike: a bad key is subtype "success" with status 401.
        _result_error(401),
        _result_error(403),
        _result_error(400),
        _result_error(None, subtype="error_max_turns", reason="max_turns"),
        _result_error(None, subtype="error_max_budget_usd", reason="max_budget"),
        CLINotFoundError("no claude"),
        CLIJSONDecodeError("{", ValueError("bad json")),
        ValueError("bug in the prompt"),
        KeyError("findings"),
    ],
    ids=lambda exc: f"{type(exc).__name__}-{getattr(exc, 'api_error_status', '')}",
)
def test_permanent_agent_errors(exc: Exception) -> None:
    assert not is_transient_agent_error(exc)


def test_retry_policy_is_one_shared_two_attempt_policy() -> None:
    assert agent.AGENT_RETRY.max_attempts == 2
    assert agent.AGENT_RETRY.retry_on is is_transient_agent_error
    assert agent.AGENT_RETRY.jitter is True
    assert agent.NODE_TIMEOUT_SECONDS == 120  # the time budget in agent.py is computed from it


@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")
def test_real_model_answers_in_the_requested_shape(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(agent, "query", real_query)
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "string"}},
        "required": ["answer"],
        "additionalProperties": False,
    }

    output = asyncio.run(
        run_agent(
            model=REVIEW_MODEL,
            system_prompt="Answer the question.",
            prompt="Reply with the single word: ok",
            output_schema=schema,
            max_turns=3,
            tools=[],
            cwd=tmp_path,
        )
    )

    assert isinstance(output["answer"], str)
