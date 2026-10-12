import json
import os
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from langgraph.types import RetryPolicy

from gha_assistant.state import ReviewState

GITHUB_API = "https://api.github.com"
GITHUB_TIMEOUT_SECONDS = 15
COMMENTS_PER_PAGE = 100

# Hidden in the rendered comment; together with a bot author it identifies our comment.
STATUS_MARKER = "<!-- gha-assistant:status -->"

_REPO_PATTERN = re.compile(r"[\w.-]+/[\w.-]+")


def is_transient_github_error(exc: Exception) -> bool:
    """Whether `exc` is a GitHub API failure worth retrying.

    Server errors, timeouts and connection failures may pass; 401/403/404 and
    other client errors never will, so they must fail the run at once.
    """
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500
    return isinstance(exc, urllib.error.URLError | TimeoutError | ConnectionError)


# Safe to retry: the only write is `upsert_comment`, which is idempotent.
GITHUB_RETRY = RetryPolicy(max_attempts=3, retry_on=is_transient_github_error)


def no_code_status(ignored: int, intent: int) -> str:
    return f"brak kodu do sprawdzenia (pominięte pliki: {ignored}, pliki Intent: {intent})"


def reviewed_status(files: int, findings: int) -> str:
    verdict = "brak uwag" if findings == 0 else f"uwagi: {findings}"
    return f"sprawdzono plików: {files}, {verdict}"


def render_status_comment(
    status: str, *, head_sha: str | None, now: datetime, summary: str = ""
) -> str:
    """Comment text without the marker. Each run overwrites the previous one, so the
    commit and time say which result the reader is looking at."""
    lines = [f"**gha-assistant:** {status}"]
    if summary:
        lines += ["", summary]
    commit = f"commit `{head_sha[:7]}`, " if head_sha else ""
    lines += ["", f"<sub>{commit}{now:%Y-%m-%d %H:%M} UTC</sub>"]
    return "\n".join(lines)


def _request(method: str, url: str, token: str, payload: dict[str, Any] | None = None) -> Any:
    """The only place that talks to GitHub; tests replace it with an in-memory fake."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "gha-assistant",
        },
    )
    with urllib.request.urlopen(request, timeout=GITHUB_TIMEOUT_SECONDS) as response:
        return json.load(response)


def _find_own_comment(repo: str, pr_number: int, token: str) -> dict[str, Any] | None:
    page = 1
    while True:
        url = (
            f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments"
            f"?per_page={COMMENTS_PER_PAGE}&page={page}"
        )
        comments = _request("GET", url, token)
        for comment in comments:
            is_bot = (comment.get("user") or {}).get("type") == "Bot"
            if is_bot and STATUS_MARKER in (comment.get("body") or ""):
                return comment
        if len(comments) < COMMENTS_PER_PAGE:
            return None
        page += 1


def upsert_comment(repo: str, pr_number: int, body: str, token: str) -> None:
    """Leave `body` as the single gha-assistant comment on the PR conversation.

    Our comment is found by the hidden marker *and* a bot author: the marker alone
    would let anyone paste it into their own comment and make us edit (or be unable
    to edit) the wrong one. It is edited in place, or created when missing, so a retry
    after a timeout never duplicates it.

    Limits: a PR from a fork gets a read-only token, so this fails there (out of scope);
    overwriting loses the previous result, which is why the body carries SHA and time.
    """
    body = f"{STATUS_MARKER}\n{body}"
    own = _find_own_comment(repo, pr_number, token)
    if own is None:
        _request(
            "POST", f"{GITHUB_API}/repos/{repo}/issues/{pr_number}/comments", token, {"body": body}
        )
    else:
        _request(
            "PATCH", f"{GITHUB_API}/repos/{repo}/issues/comments/{own['id']}", token, {"body": body}
        )


def publish_status_comment(state: ReviewState, status: str, summary: str = "") -> None:
    """Leave the run's status in the PR, or print it when `dry_run` is set.

    Without `dry_run` a missing target or token raises, so a green run always means
    the comment exists.
    """
    head_sha = state.get("head_sha")
    body = render_status_comment(status, head_sha=head_sha, now=datetime.now(UTC), summary=summary)
    if state.get("dry_run"):
        print(body)
        return

    repo, pr_number = state.get("repo"), state.get("pr_number")
    token = os.environ.get("GITHUB_TOKEN")
    missing = [
        name
        for name, value in (
            ("repo", repo),
            ("pr_number", pr_number),
            ("head_sha", head_sha),
            ("GITHUB_TOKEN", token),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"publishing the status comment requires: {', '.join(missing)}")
    assert repo and pr_number and token  # narrowed by the check above
    if not _REPO_PATTERN.fullmatch(repo):
        raise ValueError(f"invalid repo: {repo!r} (expected owner/name)")
    upsert_comment(repo, pr_number, body, token)
