from collections import Counter

from gha_assistant.finding import SEVERITY_RANK, Finding, Verdict
from gha_assistant.limits import MAX_FINDINGS
from gha_assistant.state import ReviewState


def judge_findings(state: ReviewState) -> ReviewState:
    """Closes the Review. Pure code, no model.

    The name is kept for the graph's sake; a model judge (semantic duplicates, style) was
    left out until real runs show that the Findings need it.
    """
    findings, summary = finalize_review(
        state.get("validated", []), state.get("verdicts", []), MAX_FINDINGS
    )
    return {"findings": findings, "summary": summary}


def finalize_review(
    validated: list[Finding], verdicts: list[Verdict], limit: int = MAX_FINDINGS
) -> tuple[list[Finding], str]:
    """The Findings that go to the Review, most severe first, and the summary.

    A Finding the verifier refuted is dropped; every other one stays, verified or not.
    The sort is stable, so Findings of one severity keep the order they came in.
    """
    refuted = {v["finding_id"] for v in verdicts if v["verdict"] == "refuted"}
    kept = [f for f in validated if f["id"] not in refuted]
    kept.sort(key=lambda f: SEVERITY_RANK[f["severity"]])
    findings = kept[:limit]

    parts = []
    if findings:
        by_severity = Counter(f["severity"] for f in findings)
        parts.append(
            "Wg wagi: "
            + ", ".join(f"{by_severity[s]} {s}" for s in SEVERITY_RANK if by_severity[s])
        )
    dropped = len(validated) - len(kept)
    if dropped:
        parts.append(f"obalone przez weryfikatora i odrzucone: {dropped}")
    over_limit = len(kept) - len(findings)
    if over_limit:
        parts.append(f"pominięte ponad limit {limit}: {over_limit}")
    summary = "; ".join(parts)
    return findings, summary[:1].upper() + summary[1:]
