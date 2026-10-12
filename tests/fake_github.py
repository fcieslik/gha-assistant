import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any

import pytest

from gha_assistant import github_io

_PR_COMMENTS = re.compile(r"/repos/(?P<repo>[^/]+/[^/]+)/issues/(?P<pr>\d+)/comments")
_COMMENT = re.compile(r"/repos/(?P<repo>[^/]+/[^/]+)/issues/comments/(?P<id>\d+)")


@dataclass
class FakeGitHub:
    """In-memory stand-in for the slice of the GitHub REST API that `github_io` uses."""

    comments: list[dict[str, Any]] = field(default_factory=list)
    requests: list[tuple[str, str]] = field(default_factory=list)
    tokens: set[str] = field(default_factory=set)
    # Raised before the next request is handled (the server never saw it).
    fail_next: Exception | None = None
    # Raised after the next write took effect (the client never saw the response).
    fail_after_write: Exception | None = None

    def add_comment(
        self, repo: str, pr: int, body: str, *, login: str = "someone", user_type: str = "User"
    ) -> dict[str, Any]:
        comment = {
            "id": len(self.comments) + 1,
            "repo": repo,
            "pr": pr,
            "body": body,
            "user": {"login": login, "type": user_type},
        }
        self.comments.append(comment)
        return comment

    def bodies(self) -> list[str]:
        return [comment["body"] for comment in self.comments]

    def request(
        self, method: str, url: str, token: str, payload: dict[str, Any] | None = None
    ) -> Any:
        parts = urllib.parse.urlsplit(url)
        self.requests.append((method, parts.path))
        self.tokens.add(token)
        if self.fail_next is not None:
            exc, self.fail_next = self.fail_next, None
            raise exc

        if match := _PR_COMMENTS.fullmatch(parts.path):
            repo, pr = match["repo"], int(match["pr"])
            if method == "GET":
                query = urllib.parse.parse_qs(parts.query)
                per_page, page = int(query["per_page"][0]), int(query["page"][0])
                mine = [c for c in self.comments if (c["repo"], c["pr"]) == (repo, pr)]
                return mine[(page - 1) * per_page : page * per_page]
            assert method == "POST", method
            assert payload is not None
            comment = self.add_comment(
                repo, pr, payload["body"], login="github-actions[bot]", user_type="Bot"
            )
            self._after_write()
            return comment

        if (match := _COMMENT.fullmatch(parts.path)) and method == "PATCH":
            assert payload is not None
            comment = next(c for c in self.comments if c["id"] == int(match["id"]))
            comment["body"] = payload["body"]
            self._after_write()
            return comment

        raise AssertionError(f"unexpected request: {method} {parts.path}")

    def _after_write(self) -> None:
        if self.fail_after_write is not None:
            exc, self.fail_after_write = self.fail_after_write, None
            raise exc


def install(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    fake = FakeGitHub()
    monkeypatch.setattr(github_io, "_request", fake.request)
    return fake
