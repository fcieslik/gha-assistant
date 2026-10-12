"""The one door to the Claude Agent SDK; nothing else in the project imports it.

`query()` starts a Claude Code CLI subprocess that runs the tool loop; one graph node is
one `run_agent` call. Everything that makes that safe in CI is fixed here rather than
chosen per node: read-only tools, no settings from the reviewed repository, the rules
file in the system prompt.
"""

import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    CLIConnectionError,
    CLINotFoundError,
    ProcessError,
    ResultError,
    ResultMessage,
    ToolUseBlock,
    query,
)
from langgraph.errors import NodeTimeoutError
from langgraph.types import RetryPolicy

REVIEW_MODEL = "claude-haiku-5-5"  # review_code, review_intent: many cheap reads
VERIFY_MODEL = "claude-sonnet-5-5"  # verify_finding: checks one claim, must be reliable
FALLBACK_MODEL = "claude-sonnet-5-5"

READ_ONLY_TOOLS = ("Read", "Glob", "Grep")
DEFAULT_MAX_TURNS = 30
EFFORT = "medium"  # every agent, so cost and latency do not depend on the model default
# Hard cap on one run (one attempt), enforced by the CLI; a run that hits it ends with
# `error_max_budget_usd`, which is permanent (a retry would only spend it again).
MAX_BUDGET_USD = 0.5

# `review_intent` is the one agent that is meant to go through every changed file in one
# run, so it gets more room than the per-file and per-Finding agents (30 turns, $0.5).
REVIEW_INTENT_MAX_TURNS = 100
REVIEW_INTENT_MAX_BUDGET_USD = 0.75

# Per attempt, enforced on the node (`add_node(timeout=...)`), not here: LangGraph
# raises NodeTimeoutError there, and the cancelled `query()` takes the CLI with it
# (spike: the child process was gone right after the cancellation).
NODE_TIMEOUT_SECONDS = 120

# `review_intent` goes through every changed file in one run (up to 100 turns), so one
# attempt gets 5 min. AGENT_MAX_ATTEMPTS attempts take 10 min in the worst case, in
# parallel with the `review_code` workers; verify, judge and publish still have to fit in
# the remaining 5 of the runner's 15 min. A run cut short by this is retried and costs
# another budget (up to 2 x REVIEW_INTENT_MAX_BUDGET_USD). 100 turns of Haiku can take
# longer than 5 min: not measured, only one small file set was tried.
REVIEW_INTENT_TIMEOUT_SECONDS = 300

# Time budget. One attempt gets 2 min and AGENT_RETRY allows 2 attempts, so a node can
# take 4 min plus backoff. `review_code` workers run `max_concurrency` (5) at a time, so
# N files take ceil(N/5) rounds. Measured without failures: ~6 s for a file with a 9-line
# diff (Haiku, one sample; big files are not measured). Assuming up to a minute per file,
# a round is about a minute and 15 min (`timeout-minutes`) holds roughly 75 files before
# the later stages take their share. The worst case (every file of a round times out
# twice: 4 min a round) exceeds 15 min from 4 rounds, i.e. above 15 files. We do not
# promise it: the runner kills the process and nothing is published. The stages after
# review_code are added to this estimate in tickets 06-09.
AGENT_MAX_ATTEMPTS = 2

# Retries inside the CLI. Spike: with the default, a refused connection was still being
# retried after 150 s (longer than NODE_TIMEOUT_SECONDS, so the node timeout fired first
# and then AGENT_RETRY started the whole session over); with 0 it failed in 1.1 s and
# with 1 in 1.5 s. Set explicitly: a few cheap retries inside the session are kept (they
# are what absorbs a 429/529 without redoing the turns), but bounded, so the layers
# below AGENT_RETRY cannot multiply. The backoff for 429/529 was not measured.
CLI_MAX_RETRIES = "2"

# One system prompt per agent (`prompts/<agent>.md`) plus `rules.md`, which every agent
# gets in front of its own. `rules.md` plays the part of a CLAUDE.md but is injected
# into the system prompt: the SDK would only load a real CLAUDE.md through
# `setting_sources`, which is switched off because it would read the reviewed repo's.
PROMPTS_DIR = Path(__file__).with_name("prompts")


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text().strip()


class InvalidAgentOutput(Exception):
    """The run finished but produced no structured output of the requested shape."""


# Result subtypes (from the SDK docs, not measured) that say the model's run itself went
# wrong rather than the request being doomed. `error_max_structured_output_retries` is the
# CLI's own version of `InvalidAgentOutput`. `error_during_execution` is "an error
# interrupted the loop (e.g. a cancelled request)"; its cause is unknown, and one more
# attempt is bounded by `AGENT_MAX_ATTEMPTS`. `error_max_turns` and `error_max_budget_usd`
# are absent on purpose: the same prompt would hit the same limit.
_TRANSIENT_RESULT_SUBTYPES = frozenset(
    {"error_max_structured_output_retries", "error_during_execution"}
)


def is_transient_agent_error(exc: Exception) -> bool:
    """Whether `exc` is a model-run failure worth one more attempt.

    Checks are ordered by specificity: `ResultError` and `CLINotFoundError` are
    subclasses of `ProcessError` and `CLIConnectionError`, which are transient.

    What the SDK really reports (spike, claude-agent-sdk 0.2.165):
    - a bad API key: `ResultError`, `api_error_status=401`, `subtype="success"`;
    - a refused connection: `ResultError`, `api_error_status=None`,
      `terminal_reason="api_error"` (not a connection error type);
    - too many turns: `ResultError`, `subtype="error_max_turns"`, no status.
    `subtype` alone says nothing for API failures: it was "success" for the first two.
    """
    if isinstance(exc, NodeTimeoutError | InvalidAgentOutput):
        return True
    if isinstance(exc, CLINotFoundError):
        return False
    if isinstance(exc, ResultError):
        status = exc.api_error_status
        if status is None:
            return exc.subtype in _TRANSIENT_RESULT_SUBTYPES or exc.terminal_reason == "api_error"
        return status in (429, 529) or status >= 500
    return isinstance(exc, CLIConnectionError | ProcessError)


# One policy for every node with a model; each node still decides how to degrade once it
# is exhausted. Safe to retry because every model run is read-only. Jitter stays on:
# `Send` workers hit the API in parallel.
AGENT_RETRY = RetryPolicy(max_attempts=AGENT_MAX_ATTEMPTS, retry_on=is_transient_agent_error)


LOG_LINE_LIMIT = 120


def _one_line(text: object) -> str:
    """Untrusted text made safe for one line of the Actions log: no newlines or control
    characters, and shortened. The caller puts its own `[label]` in front, so a line can
    never start with `::` (the runner would run it as a workflow command)."""
    cleaned = "".join(c if c.isprintable() else " " for c in str(text))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > LOG_LINE_LIMIT:
        cleaned = cleaned[: LOG_LINE_LIMIT - 1] + "…"
    return cleaned


def _log(label: str, text: str) -> None:
    # stderr and flushed: stdout is block-buffered without a TTY, so a CI log would show
    # nothing until the process exits. The label tells parallel workers apart.
    print(f"[{_one_line(label)}] {text}", file=sys.stderr, flush=True)


def _log_message(label: str, message: object) -> None:
    """Which tools the agent calls and how the run ended; never the model's own text,
    which may quote secrets or PR content, and the Actions log is as public as the repo."""
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, ToolUseBlock):
                target = next(
                    (block.input[k] for k in ("file_path", "path", "pattern") if k in block.input),
                    "",
                )
                _log(label, _one_line(f"{block.name} {target}"))
    elif isinstance(message, ResultMessage):
        cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd is not None else "n/a"
        _log(
            label,
            f"{message.subtype}{' (error)' if message.is_error else ''}: "
            f"turns={message.num_turns} cost={cost} duration={message.duration_ms / 1000:.1f}s",
        )


def build_options(
    *,
    model: str,
    system_prompt: str,
    output_schema: dict[str, Any],
    max_turns: int,
    max_budget_usd: float,
    tools: Sequence[str],
    cwd: str | Path | None,
) -> ClaudeAgentOptions:
    tool_list = list(tools)
    return ClaudeAgentOptions(
        model=model,
        # Not offered at all (`tools`), pre-approved (`allowed_tools`), and anything
        # else is refused instead of prompting (`dontAsk`); `allowed_tools` alone hides nothing.
        tools=tool_list,
        allowed_tools=tool_list,
        permission_mode="dontAsk",
        # No CLAUDE.md or `.claude/` from the reviewed repository: it is PR content.
        setting_sources=[],
        system_prompt=f"{load_prompt('rules')}\n\n{system_prompt}",
        output_format={"type": "json_schema", "schema": output_schema},
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        effort=EFFORT,
        # A fallback equal to the model is rejected by the CLI.
        fallback_model=FALLBACK_MODEL if model != FALLBACK_MODEL else None,
        cwd=cwd,
        env={"CLAUDE_CODE_MAX_RETRIES": CLI_MAX_RETRIES},
    )


async def run_agent(
    model: str,
    system_prompt: str,
    prompt: str,
    output_schema: dict[str, Any],
    max_turns: int = DEFAULT_MAX_TURNS,
    max_budget_usd: float = MAX_BUDGET_USD,
    tools: Sequence[str] = READ_ONLY_TOOLS,
    cwd: str | Path | None = None,
    label: str = "agent",
) -> dict[str, Any]:
    """Run the model once and return its structured output.

    A failed run raises `ResultError` (or another SDK error); an answer that does not
    come in the requested shape raises `InvalidAgentOutput`. `label` prefixes the
    progress lines (tool calls, final cost) written to stderr for the CI log.
    """
    options = build_options(
        model=model,
        system_prompt=system_prompt,
        output_schema=output_schema,
        max_turns=max_turns,
        max_budget_usd=max_budget_usd,
        tools=tools,
        cwd=cwd,
    )
    result: ResultMessage | None = None
    # Read the stream to its end: for a failed run the SDK yields the error result first
    # and raises `ResultError` afterwards, so returning early would swallow the error.
    async for message in query(prompt=prompt, options=options):
        _log_message(label, message)
        if isinstance(message, ResultMessage):
            result = message
    if result is None:
        raise InvalidAgentOutput("the run ended without a result")
    if result.is_error:
        # The SDK raises `ResultError` itself after yielding an error result. Should it
        # ever not, raise the same type so `is_transient_agent_error` decides by subtype
        # and status instead of this being retried as invalid output.
        raise ResultError(
            f"the run failed: {result.subtype}",
            data={
                "subtype": result.subtype,
                "api_error_status": result.api_error_status,
                "terminal_reason": result.terminal_reason,
                "errors": result.errors,
                "result": result.result,
            },
        )
    if not isinstance(result.structured_output, dict):
        raise InvalidAgentOutput("the run produced no structured output")
    return result.structured_output
