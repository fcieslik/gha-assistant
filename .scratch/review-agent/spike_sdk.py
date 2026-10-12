"""Spike for ticket 04: what the Claude Agent SDK really does. Not part of `src`.

Run one probe at a time:  uv run --env-file .env python .scratch/review-agent/spike_sdk.py <probe>

  structured   structured_output against a JSON schema
  tools        Bash/Write must be refused with tools + allowed_tools + dontAsk
  retry        how long the CLI retries a connection error (default vs CLAUDE_CODE_MAX_RETRIES)
  hang         does cancelling query() (what a node timeout does) kill the CLI process
"""

import asyncio
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ResultError,
    ResultMessage,
    SystemMessage,
    query,
)

HAIKU = "claude-haiku-5-5"
SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "numbers": {"type": "array", "items": {"type": "integer"}},
    },
    "required": ["answer", "numbers"],
    "additionalProperties": False,
}


def options(cwd: str, **overrides) -> ClaudeAgentOptions:
    base = dict(
        model=HAIKU,
        cwd=cwd,
        tools=["Read", "Glob", "Grep"],
        allowed_tools=["Read", "Glob", "Grep"],
        permission_mode="dontAsk",
        setting_sources=[],
        max_turns=5,
    )
    base.update(overrides)
    return ClaudeAgentOptions(**base)


async def run(prompt: str, opts: ClaudeAgentOptions) -> list:
    messages = []
    async for message in query(prompt=prompt, options=opts):
        messages.append(message)
    return messages


def summarize(messages: list) -> None:
    for message in messages:
        if isinstance(message, SystemMessage) and message.subtype == "init":
            print("init tools:", message.data.get("tools"))
        if isinstance(message, ResultMessage):
            print("subtype:", message.subtype, "| is_error:", message.is_error)
            print("structured_output:", message.structured_output)
            print("permission_denials:", message.permission_denials)
            print("turns:", message.num_turns, "| cost:", message.total_cost_usd)


async def probe_structured() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "data.txt").write_text("alpha beta\n1 2 3\n")
        opts = options(
            tmp, output_format={"type": "json_schema", "schema": SCHEMA}
        )
        summarize(
            await run(
                "Read data.txt. Return the first word as `answer` and the integers as `numbers`.",
                opts,
            )
        )


async def probe_tools() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        opts = options(tmp, output_format={"type": "json_schema", "schema": SCHEMA})
        messages = await run(
            f"Run `echo pwned > {tmp}/bash.txt` with Bash, then create {tmp}/write.txt with "
            "the Write tool. If a tool is not available say so in `answer`; numbers = [].",
            opts,
        )
        summarize(messages)
        print("files created:", sorted(p.name for p in Path(tmp).iterdir()))


async def probe_retry() -> None:
    for retries in (None, "0", "1"):
        env = {"ANTHROPIC_BASE_URL": "http://127.0.0.1:9"}
        if retries is not None:
            env["CLAUDE_CODE_MAX_RETRIES"] = retries
        with tempfile.TemporaryDirectory() as tmp:
            started = time.monotonic()
            try:
                await asyncio.wait_for(run("hi", options(tmp, env=env, max_turns=1)), 150)
                outcome = "no error"
            except TimeoutError:
                outcome = "STILL RUNNING after 150 s"
            except ResultError as exc:
                outcome = (
                    f"ResultError subtype={exc.subtype} status={exc.api_error_status} "
                    f"reason={exc.terminal_reason} result={exc.result!r:.120}"
                )
            except Exception as exc:  # noqa: BLE001 - a spike reports whatever comes out
                outcome = f"{type(exc).__name__}: {exc!s:.200}"
            print(f"MAX_RETRIES={retries!r}: {time.monotonic() - started:.1f}s -> {outcome}")


async def probe_hang() -> None:
    async def never_answer_quiet(reader, writer):
        try:
            await reader.read()
        except ConnectionError:
            pass

    server = await asyncio.start_server(never_answer_quiet, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    env = {"ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}", "CLAUDE_CODE_MAX_RETRIES": "0"}

    def children() -> list[str]:
        # Only direct children of this process: the machine runs other Claude sessions.
        out = subprocess.run(
            ["ps", "-ax", "-o", "pid=,ppid=,command="], capture_output=True, text=True
        ).stdout
        mine = str(os.getpid())
        return [
            line.strip()[:90] for line in out.splitlines() if line.split()[1:2] == [mine]
        ]

    async def watch(seen: list[str]) -> None:
        await asyncio.sleep(4)
        seen.extend(children())

    seen: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        watcher = asyncio.create_task(watch(seen))
        try:
            await asyncio.wait_for(run("hi", options(tmp, env=env, max_turns=1)), 8)
        except TimeoutError:
            print("cancelled after 8 s (what a node timeout does)")
        await watcher
    print("children while running:", seen or "none")
    for seconds in (0, 2, 5):
        await asyncio.sleep(seconds)
        print(f"children {seconds}s after cancel:", children() or "none")
    server.close()


async def probe_badkey() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        started = time.monotonic()
        try:
            await run("hi", options(tmp, env={"ANTHROPIC_API_KEY": "sk-ant-bad"}, max_turns=1))
        except Exception as exc:  # noqa: BLE001
            print(f"{time.monotonic() - started:.1f}s", type(exc).__mro__[:3])
            for name in ("subtype", "api_error_status", "terminal_reason", "result", "exit_code"):
                print(" ", name, "=", repr(getattr(exc, name, "-"))[:150])


async def probe_maxturns() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "a.txt").write_text("a")
        (Path(tmp) / "b.txt").write_text("b")
        try:
            await run(
                "Read a.txt, then b.txt, then Glob *.txt, one tool call per turn.",
                options(tmp, max_turns=1),
            )
            print("no error")
        except Exception as exc:  # noqa: BLE001
            print(type(exc).__name__)
            for name in ("subtype", "api_error_status", "terminal_reason", "errors", "exit_code"):
                print(" ", name, "=", repr(getattr(exc, name, "-"))[:150])


async def probe_notools() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        opts = options(
            tmp,
            tools=[],
            allowed_tools=[],
            output_format={"type": "json_schema", "schema": SCHEMA},
        )
        summarize(await run("Reply answer='ok', numbers=[1].", opts))


PROBES = {
    "notools": probe_notools,
    "badkey": probe_badkey,
    "maxturns": probe_maxturns,
    "structured": probe_structured,
    "tools": probe_tools,
    "retry": probe_retry,
    "hang": probe_hang,
}

if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set (use `uv run --env-file .env`)")
    asyncio.run(PROBES[sys.argv[1]]())
