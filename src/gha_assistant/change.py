import subprocess
from pathlib import Path
from typing import TypedDict


class Change(TypedDict):
    intent: list[str]
    code: list[str]
    ignored: list[str]


def collect_change(base_ref: str, repo: Path) -> Change:
    """List the files changed by the PR checked out in `repo`.

    The three-dot diff compares against the merge base, so commits that
    reached `base_ref` after the PR branched off are left out.
    """
    result = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-status", "-M", f"{base_ref}...HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return _parse_name_status(result.stdout)


def _parse_name_status(text: str) -> Change:
    change: Change = {"intent": [], "code": [], "ignored": []}
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status = fields[0][0]
        # Renames and copies are "R100<TAB>old<TAB>new"; only the new path counts.
        path = fields[-1]
        if status == "D":
            change["ignored"].append(path)
        else:
            change["code"].append(path)
    return {
        "intent": sorted(change["intent"]),
        "code": sorted(change["code"]),
        "ignored": sorted(change["ignored"]),
    }
