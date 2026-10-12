import urllib.error
from datetime import UTC, datetime
from email.message import Message

import pytest
from fake_github import FakeGitHub

from gha_assistant import github_io
from gha_assistant.finding import Finding
from gha_assistant.github_io import (
    STATUS_MARKER,
    is_transient_github_error,
    no_code_status,
    publish_status_comment,
    render_status_comment,
    reviewed_status,
    upsert_comment,
)
from gha_assistant.state import ReviewState

REPO = "octo/repo"
NOW = datetime(2026, 10, 12, 14, 30, tzinfo=UTC)


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.github.com", code, "boom", Message(), None)


@pytest.mark.parametrize(
    ("exc", "transient"),
    [
        (http_error(500), True),
        (http_error(502), True),
        (http_error(503), True),
        (http_error(401), False),
        (http_error(403), False),
        (http_error(404), False),
        (TimeoutError(), True),
        (ConnectionResetError(), True),
        (urllib.error.URLError("name resolution failed"), True),
        (ValueError("missing token"), False),
    ],
)
def test_is_transient_github_error(exc: Exception, transient: bool) -> None:
    assert is_transient_github_error(exc) is transient


def test_render_has_status_summary_commit_and_time() -> None:
    body = render_status_comment(
        "sprawdzono plików: 3, brak uwag",
        head_sha="0123456789abcdef",
        now=NOW,
        summary="Wszystko wygląda dobrze.",
    )

    assert body.splitlines()[0] == "**gha-assistant:** sprawdzono plików: 3, brak uwag"
    assert "Wszystko wygląda dobrze." in body
    assert "0123456" in body
    assert "2026-10-12 14:30 UTC" in body


def test_render_without_summary_has_no_empty_section() -> None:
    body = render_status_comment("status", head_sha=None, now=NOW)

    assert body.splitlines() == ["**gha-assistant:** status", "", "<sub>2026-10-12 14:30 UTC</sub>"]


def test_render_lists_warnings_as_one_line_code_spans() -> None:
    body = render_status_comment(
        "status", head_sha=None, now=NOW, warnings=["pierwsze", "drugie `z` backtickiem"]
    )

    assert "**Ostrzeżenia:**" in body
    assert "- `pierwsze`" in body
    assert "- `drugie 'z' backtickiem`" in body


def test_render_keeps_hostile_warning_text_inert() -> None:
    hostile = "plik @octocat\n[link](http://x) <img src=x>\x1b[31m" + "a" * 500

    body = render_status_comment("status", head_sha=None, now=NOW, warnings=[hostile])

    (line,) = [ln for ln in body.splitlines() if ln.startswith("- ")]
    assert line.startswith("- `plik @octocat [link](http://x) <img src=x>")
    assert line.endswith("…`")
    assert len(line) < 220
    assert "\x1b" not in body


def test_render_caps_the_number_of_warnings() -> None:
    warnings = [f"w{n}" for n in range(github_io.MAX_WARNINGS_SHOWN + 3)]

    body = render_status_comment("status", head_sha=None, now=NOW, warnings=warnings)

    assert f"- `w{github_io.MAX_WARNINGS_SHOWN - 1}`" in body
    assert f"- `w{github_io.MAX_WARNINGS_SHOWN}`" not in body
    assert "- i 3 więcej" in body


def test_render_without_warnings_has_no_warnings_section() -> None:
    assert "Ostrzeżenia" not in render_status_comment("status", head_sha=None, now=NOW)


def _finding(**fields: object) -> Finding:
    finding: dict[str, object] = {
        "id": "f1",
        "source": "code",
        "severity": "high",
        "message": "Wynik nie jest sprawdzany.",
    }
    finding.update(fields)
    return finding  # type: ignore[return-value]


def test_render_lists_findings_with_severity_place_message_and_suggestion() -> None:
    finding = _finding(file="src/a.py", line=12, suggestion="Dodaj `if`.")

    body = render_status_comment("status", head_sha=None, now=NOW, findings=[finding])

    assert "**Uwagi:**" in body
    assert "- **high** `src/a.py:12`" in body
    assert "  `Wynik nie jest sprawdzany.`" in body
    assert "  Sugestia: `Dodaj 'if'.`" in body


def test_render_a_finding_without_a_place_is_a_general_remark() -> None:
    finding = _finding(severity="medium", spec_ref=".scratch/x/spec.md: kryterium 2")

    body = render_status_comment("status", head_sha=None, now=NOW, findings=[finding])

    assert "- **medium** uwaga ogólna" in body
    assert "  Wymaganie: `.scratch/x/spec.md: kryterium 2`" in body


def test_render_a_finding_without_a_line_shows_only_the_file() -> None:
    body = render_status_comment("status", head_sha=None, now=NOW, findings=[_finding(file="a.py")])

    assert "- **high** `a.py`" in body


def test_render_keeps_hostile_finding_text_inert() -> None:
    hostile = "@octocat [link](http://x) ![](http://x/p.png) <img src=x>\n\x1b[31m" + "a" * 900
    finding = _finding(message=hostile, suggestion=hostile, file="@octocat/<b>.py", line=3)

    body = render_status_comment("status", head_sha=None, now=NOW, findings=[finding])

    lines = [ln for ln in body.splitlines() if ln.startswith(("- ", "  "))]
    assert len(lines) == 3
    assert all("`" in ln and len(ln) < 700 for ln in lines)
    assert lines[0].startswith("- **high** `@octocat/<b>.py:3`")
    assert "\x1b" not in body


def test_render_without_findings_has_no_findings_section() -> None:
    assert "Uwagi" not in render_status_comment("status", head_sha=None, now=NOW)


def test_publish_status_comment_posts_the_findings(fake_github: FakeGitHub) -> None:
    publish_status_comment(_state(), "status", findings=[_finding(file="a.py", line=1)])

    assert "- **high** `a.py:1`" in fake_github.comments[0]["body"]


def test_status_variants() -> None:
    assert no_code_status(ignored=3, intent=1) == (
        "brak kodu do sprawdzenia (pominięte pliki: 3, pliki Intent: 1)"
    )
    assert reviewed_status(files=2, findings=0) == "sprawdzono plików: 2, brak uwag"
    assert reviewed_status(files=2, findings=4) == "sprawdzono plików: 2, uwagi: 4"


def test_upsert_creates_comment_when_there_is_none(fake_github: FakeGitHub) -> None:
    upsert_comment(REPO, 7, "first", "test-token")

    assert len(fake_github.comments) == 1
    assert STATUS_MARKER in fake_github.comments[0]["body"]
    assert fake_github.comments[0]["body"].endswith("first")


def test_second_run_edits_the_comment_instead_of_adding_one(fake_github: FakeGitHub) -> None:
    upsert_comment(REPO, 7, "first", "test-token")
    upsert_comment(REPO, 7, "second", "test-token")

    assert len(fake_github.comments) == 1
    assert fake_github.comments[0]["body"].endswith("second")
    assert [method for method, _ in fake_github.requests].count("POST") == 1


def test_someone_elses_comment_with_the_marker_is_left_alone(fake_github: FakeGitHub) -> None:
    pasted = fake_github.add_comment(REPO, 7, f"{STATUS_MARKER}\nlooks official", user_type="User")

    upsert_comment(REPO, 7, "ours", "test-token")

    assert pasted["body"] == f"{STATUS_MARKER}\nlooks official"
    assert len(fake_github.comments) == 2
    assert fake_github.comments[1]["user"]["type"] == "Bot"
    assert fake_github.comments[1]["body"].endswith("ours")


def test_bot_comment_without_the_marker_is_left_alone(fake_github: FakeGitHub) -> None:
    other_bot = fake_github.add_comment(
        REPO, 7, "coverage report", login="codecov[bot]", user_type="Bot"
    )

    upsert_comment(REPO, 7, "ours", "test-token")

    assert other_bot["body"] == "coverage report"
    assert len(fake_github.comments) == 2


def test_own_comment_is_found_beyond_the_first_page(
    fake_github: FakeGitHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(github_io, "COMMENTS_PER_PAGE", 2)
    for n in range(3):
        fake_github.add_comment(REPO, 7, f"chatter {n}")
    own = fake_github.add_comment(
        REPO, 7, f"{STATUS_MARKER}\nold", login="github-actions[bot]", user_type="Bot"
    )

    upsert_comment(REPO, 7, "new", "test-token")

    assert len(fake_github.comments) == 4
    assert own["body"].endswith("new")


def test_comments_of_other_prs_are_not_touched(fake_github: FakeGitHub) -> None:
    other = fake_github.add_comment(
        REPO, 8, f"{STATUS_MARKER}\nother pr", login="github-actions[bot]", user_type="Bot"
    )

    upsert_comment(REPO, 7, "ours", "test-token")

    assert other["body"].endswith("other pr")
    assert len(fake_github.comments) == 2


def _state(**overrides: object) -> ReviewState:
    state: dict[str, object] = {
        "repo": REPO,
        "pr_number": 7,
        "head_sha": "0123456789abcdef",
        "dry_run": False,
    }
    state.update(overrides)
    return state  # type: ignore[return-value]


def test_publish_status_comment_uses_token_from_environment(fake_github: FakeGitHub) -> None:
    publish_status_comment(_state(), "status", summary="summary text")

    assert fake_github.tokens == {"test-token"}
    assert len(fake_github.comments) == 1
    body = fake_github.comments[0]["body"]
    assert "status" in body
    assert "summary text" in body
    assert "0123456" in body


@pytest.mark.parametrize("missing", ["repo", "pr_number", "head_sha"])
def test_missing_target_fails_instead_of_staying_silent(
    fake_github: FakeGitHub, missing: str
) -> None:
    state = _state()
    del state[missing]  # type: ignore[misc]

    with pytest.raises(ValueError, match=missing):
        publish_status_comment(state, "status")

    assert fake_github.requests == []


def test_missing_token_fails_instead_of_staying_silent(
    fake_github: FakeGitHub, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN")

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        publish_status_comment(_state(), "status")

    assert fake_github.requests == []


@pytest.mark.parametrize("repo", ["../etc/passwd", "owner", "owner/name/extra", "owner/na me"])
def test_malformed_repo_never_reaches_the_url(fake_github: FakeGitHub, repo: str) -> None:
    with pytest.raises(ValueError, match="repo"):
        publish_status_comment(_state(repo=repo), "status")

    assert fake_github.requests == []


def test_dry_run_prints_the_comment_and_sends_nothing(
    fake_github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN")

    publish_status_comment({"dry_run": True}, "brak kodu do sprawdzenia", summary="notes")

    out = capsys.readouterr().out
    assert "brak kodu do sprawdzenia" in out
    assert "notes" in out
    assert fake_github.requests == []
