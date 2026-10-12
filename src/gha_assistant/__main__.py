"""Entry point: `python -m gha_assistant`.

In GitHub Actions the run is described by the `pull_request` event file; locally,
`--dry-run --base-ref origin/main` reviews the current checkout and prints the comment.
"""

import argparse
import asyncio
import json
import os
import sys
import traceback
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from gha_assistant.graph import build_graph
from gha_assistant.state import ReviewState

_MESSAGE_CHARS = 500


class UsageError(Exception):
    """The run was started wrongly (missing environment, wrong event). Not a model failure."""


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="gha_assistant", description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="print the comment instead of posting it"
    )
    parser.add_argument(
        "--base-ref",
        help="git ref of the PR base, e.g. origin/main; only for runs without a PR event",
    )
    parser.add_argument(
        "--repo-path",
        help="checkout to review (default: GITHUB_WORKSPACE, then the current directory)",
    )
    return parser.parse_args(argv)


def _is_fork(pull_request: Mapping[str, Any]) -> bool:
    """A PR from a fork gets a read-only token and no secrets, so the run could not publish."""
    head = (pull_request.get("head") or {}).get("repo") or {}
    base = (pull_request.get("base") or {}).get("repo") or {}
    return head.get("full_name") != base.get("full_name")


def build_state(
    args: argparse.Namespace, env: Mapping[str, str]
) -> tuple[ReviewState, Mapping[str, Any] | None]:
    """The graph input and, when there is a PR event, its `pull_request` object."""
    repo_path = args.repo_path or env.get("GITHUB_WORKSPACE") or str(Path.cwd())
    event_path = env.get("GITHUB_EVENT_PATH")

    if not event_path:
        if not (args.base_ref and args.dry_run):
            raise UsageError(
                "without a pull_request event (GITHUB_EVENT_PATH) run with "
                "--dry-run and --base-ref, e.g. --base-ref origin/main"
            )
        state: ReviewState = {
            "base_ref": args.base_ref,
            "repo_path": repo_path,
            "pr_title": "",
            "pr_body": "",
            "dry_run": True,
        }
        return state, None

    try:
        event = json.loads(Path(event_path).read_text())
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot read the event file {event_path}: {exc}") from exc
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        raise UsageError(
            "the event has no pull_request: run the workflow on `pull_request`, not on push"
        )
    try:
        state = {
            # `actions/checkout` with fetch-depth 0 leaves the base as `origin/<branch>`.
            "base_ref": args.base_ref or f"origin/{pull_request['base']['ref']}",
            "repo_path": repo_path,
            "pr_title": pull_request.get("title") or "",
            "pr_body": pull_request.get("body") or "",
            "repo": env.get("GITHUB_REPOSITORY") or pull_request["base"]["repo"]["full_name"],
            "pr_number": pull_request["number"],
            "head_sha": pull_request["head"]["sha"],
            "dry_run": args.dry_run,
        }
    except (KeyError, TypeError) as exc:
        raise UsageError(f"the pull_request event misses a field: {exc}") from exc
    return state, pull_request


def _report_error(message: str, env: Mapping[str, str]) -> None:
    """One line: a workflow annotation in Actions, plain text elsewhere."""
    line = " ".join(message.split())
    if len(line) > _MESSAGE_CHARS:
        line = line[: _MESSAGE_CHARS - 1] + "…"
    prefix = "::error::" if env.get("GITHUB_ACTIONS") == "true" else "error: "
    print(f"{prefix}gha-assistant: {line}", file=sys.stderr)


def main(argv: Sequence[str] | None = None, env: Mapping[str, str] | None = None) -> int:
    """Exit codes: 0 done (or skipped), 1 the run failed, 2 the run was started wrongly."""
    env = os.environ if env is None else env
    args = parse_args(argv)
    try:
        state, pull_request = build_state(args, env)
        # Before the key check: a fork run has no secrets, and that is not an error.
        if pull_request is not None and _is_fork(pull_request):
            print(
                "gha-assistant: PR from a fork has a read-only token and no secrets; skipped",
                file=sys.stderr,
            )
            return 0
        if not env.get("ANTHROPIC_API_KEY"):
            raise UsageError("ANTHROPIC_API_KEY is not set")
    except UsageError as exc:
        _report_error(str(exc), env)
        return 2

    try:
        asyncio.run(build_graph().ainvoke(state))
    except Exception as exc:
        _report_error(f"{type(exc).__name__}: {exc}", env)
        traceback.print_exc()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
