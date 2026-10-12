import subprocess
from pathlib import Path, PurePosixPath
from typing import Literal, TypedDict


class Change(TypedDict):
    intent: list[str]
    code: list[str]
    ignored: list[str]


# Source of truth for classification. The `paths-ignore` filter in the target
# repository's workflow (docs/PROJECT_GOAL.md) mirrors the documentation part
# of IGNORED_PATTERNS; keep the two in sync by hand.
INTENT_PATTERNS = (
    ".scratch/**/*.md",
    "docs/adr/**/*.md",
)
IGNORED_PATTERNS = (
    "**/*.lock",
    "**/package-lock.json",
    "**/pnpm-lock.yaml",
    "**/dist/**",
    "**/*.min.*",
    "**/*.md",
    "docs/**",
)
BINARY_SUFFIXES = frozenset(
    {
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff",
        ".pdf", ".zip", ".gz", ".tar", ".tgz", ".7z", ".jar", ".whl", ".so",
        ".dll", ".exe", ".bin", ".pyc", ".woff", ".woff2", ".ttf", ".otf",
        ".eot", ".mp3", ".mp4", ".wav", ".mov", ".webm",
    }
)  # fmt: skip


GIT_TIMEOUT_SECONDS = 45


def collect_change(base_ref: str, repo: Path) -> Change:
    """List the files changed by the PR checked out in `repo`.

    The three-dot diff compares against the merge base, so commits that
    reached `base_ref` after the PR branched off are left out.
    """
    _check_base_ref(base_ref)
    result = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-status", "-M", f"{base_ref}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    return _parse_name_status(result.stdout)


def file_diff(base_ref: str, repo: Path, path: str) -> str:
    """The PR's diff of one file, same comparison as `collect_change`.

    The reviewing agent has no `git`, so the diff goes into its prompt as data.
    """
    _check_base_ref(base_ref)
    result = subprocess.run(
        ["git", "-C", str(repo), "diff", f"{base_ref}...HEAD", "--", path],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    return result.stdout


def _check_base_ref(base_ref: str) -> None:
    # `base_ref` becomes part of a git argument; a leading dash would be read as an option.
    if not base_ref or base_ref.startswith("-"):
        raise ValueError(f"invalid base_ref: {base_ref!r}")


def _parse_name_status(text: str) -> Change:
    change: Change = {"intent": [], "code": [], "ignored": []}
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status = fields[0][0]
        # Renames and copies are "R100<TAB>old<TAB>new"; only the new path counts.
        path = fields[-1]
        change[_classify(status, path)].append(path)
    return {
        "intent": sorted(change["intent"]),
        "code": sorted(change["code"]),
        "ignored": sorted(change["ignored"]),
    }


def _classify(status: str, path: str) -> Literal["intent", "code", "ignored"]:
    # Rules run in this order; the first match wins.
    if status == "D":
        return "ignored"
    posix = PurePosixPath(path)
    if _matches(posix, INTENT_PATTERNS):
        return "intent"
    if _matches(posix, IGNORED_PATTERNS) or posix.suffix.lower() in BINARY_SUFFIXES:
        return "ignored"
    return "code"


def _matches(path: PurePosixPath, patterns: tuple[str, ...]) -> bool:
    return any(path.full_match(pattern) for pattern in patterns)
