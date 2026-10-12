import operator
from typing import Annotated, TypedDict

from gha_assistant.change import Change
from gha_assistant.finding import Finding, Verdict


class ReviewState(TypedDict, total=False):
    base_ref: str
    repo_path: str
    pr_title: str
    pr_body: str
    # Publication target. The token is deliberately not here: state ends up in
    # `stream_mode` output and logs, so it is read from GITHUB_TOKEN instead.
    repo: str  # "owner/name"
    pr_number: int
    head_sha: str  # PR branch tip (github.event.pull_request.head.sha), not GITHUB_SHA
    dry_run: bool
    change: Change
    # Stage fields. Parallel workers write to the ones with a reducer: without it the
    # last writer would win and a reviewer's remarks would silently vanish.
    candidates: Annotated[list[Finding], operator.add]  # from review_code / review_intent
    validated: list[Finding]  # after validate_findings
    verdicts: Annotated[list[Verdict], operator.add]  # from verify_finding
    findings: list[Finding]  # final, after judge_findings
    warnings: Annotated[list[str], operator.add]  # degradation notes
    summary: str
