from collections.abc import Callable, Collection
from pathlib import Path
from typing import Literal

from langgraph.types import Send

from gha_assistant.finding import Finding
from gha_assistant.state import ReviewState

# Only `high` Findings are verified, and at most this many; every other Finding goes on
# to the judge unverified.
MAX_VERIFICATIONS = 10

_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def validate_findings(state: ReviewState) -> ReviewState:
    """Drop the Findings that point at places which do not exist. Pure code, no model.

    Line numbers refer to the file as the PR leaves it, which is the checked-out
    working tree (the same one the reviewing agents read).
    """
    repo = Path(state["repo_path"])
    validated, warnings = check_findings(
        state.get("candidates", []),
        code=state["change"]["code"],
        read_lines=lambda path: _read_lines(repo / path),
    )
    return {"validated": validated, "warnings": warnings}


def check_findings(
    candidates: list[Finding],
    code: Collection[str],
    read_lines: Callable[[str], list[str]],
) -> tuple[list[Finding], list[str]]:
    """The Findings that survive and one warning per Finding that did not.

    `code` is `change["code"]`; `read_lines` gives a file's lines and is only asked about
    files that are in `code`.
    """
    cache: dict[str, list[str]] = {}

    def lines_of(path: str) -> list[str]:
        if path not in cache:
            cache[path] = read_lines(path)
        return cache[path]

    kept: dict[tuple[object, ...], Finding] = {}
    warnings: list[str] = []
    for finding in candidates:
        reason = _rejection(finding, code, lines_of)
        if reason:
            warnings.append(f"odrzucono uwagę {finding['id']}: {reason}")
            continue
        key = _duplicate_key(finding)
        earlier = kept.get(key)
        if earlier is None:
            kept[key] = finding
            continue
        # The same place and source twice: one stays, the more severe of the two.
        dropped = finding
        if _SEVERITY_RANK[finding["severity"]] < _SEVERITY_RANK[earlier["severity"]]:
            kept[key], dropped = finding, earlier
        warnings.append(f"odrzucono uwagę {dropped['id']}: duplikat uwagi z tego samego miejsca")
    return list(kept.values()), warnings


def _rejection(
    finding: Finding, code: Collection[str], lines_of: Callable[[str], list[str]]
) -> str | None:
    path, line = finding.get("file"), finding.get("line")
    if finding["source"] == "spec" and not finding.get("spec_ref"):
        return "uwaga ze źródła spec bez spec_ref"
    if path is None:
        if line is not None:
            return f"linia {line} bez pliku"
        # A general remark has no place to be checked against, so the spec is its anchor.
        if not finding.get("spec_ref"):
            return "uwaga ogólna (bez pliku i linii) bez spec_ref"
        return None
    if path not in code:
        return f"plik {path} nie należy do zmienionego kodu"
    if line is None:
        return None
    lines = lines_of(path)
    if not 1 <= line <= len(lines):
        return f"linia {line} poza plikiem {path} ({len(lines)} linii)"
    evidence = finding.get("evidence", "").strip()
    if evidence and evidence not in lines[line - 1]:
        return f"cytat nie występuje w {path}:{line}"
    return None


def _duplicate_key(finding: Finding) -> tuple[object, ...]:
    if "file" in finding:
        return (finding["file"], finding.get("line"), finding["source"])
    # General remarks share no place; telling them apart by criterion and wording keeps
    # two unmet criteria from collapsing into one.
    return (None, finding["source"], finding.get("spec_ref"), finding["message"])


def _read_lines(path: Path) -> list[str]:
    """Lines as GitHub numbers them (split on newline only); `[]` for what cannot be read."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # the newline that ends the last line starts no new one
    return lines


def route_after_validation(state: ReviewState) -> Literal["publish", "judge_findings"] | list[Send]:
    """Next step once the Findings are validated.

    Only `high` Findings are verified. An empty list of `Send` would end the branch and
    the graph without reaching the next node, so each "nothing to verify" case is routed
    explicitly: no Findings at all goes to `publish`, no `high` one to `judge_findings`.
    """
    validated = state.get("validated", [])
    if not validated:
        return "publish"
    high = [f for f in validated if f["severity"] == "high"][:MAX_VERIFICATIONS]
    if not high:
        return "judge_findings"
    repo_path = state["repo_path"]
    return [Send("verify_finding", {"finding": f, "repo_path": repo_path}) for f in high]
