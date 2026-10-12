import pytest

from gha_assistant.finding import Finding, Severity, Verdict, VerdictKind
from gha_assistant.nodes.judge_findings import MAX_FINDINGS, finalize_review


def finding(id: str, severity: Severity = "low") -> Finding:
    return {"id": id, "source": "code", "severity": severity, "message": "m", "file": "a.py"}


def verdict(finding_id: str, kind: VerdictKind) -> Verdict:
    return {"finding_id": finding_id, "verdict": kind, "reason": "r"}


def ids(findings: list[Finding]) -> list[str]:
    return [f["id"] for f in findings]


def test_the_cap_is_fifteen() -> None:
    assert MAX_FINDINGS == 15


def test_nothing_to_close_gives_an_empty_review() -> None:
    assert finalize_review([], []) == ([], "")


def test_findings_come_out_most_severe_first_and_keep_their_order_within_a_severity() -> None:
    validated = [
        finding("l1", "low"),
        finding("h1", "high"),
        finding("m1", "medium"),
        finding("h2", "high"),
        finding("l2", "low"),
    ]

    findings, _ = finalize_review(validated, [])

    assert ids(findings) == ["h1", "h2", "m1", "l1", "l2"]


@pytest.mark.parametrize(
    ("kind", "stays"),
    [("confirmed", True), ("inconclusive", True), ("refuted", False)],
)
def test_only_a_refuted_finding_is_dropped(kind: VerdictKind, stays: bool) -> None:
    findings, _ = finalize_review([finding("a", "high")], [verdict("a", kind)])

    assert ids(findings) == (["a"] if stays else [])


def test_a_finding_without_a_verdict_stays() -> None:
    findings, _ = finalize_review([finding("a", "medium")], [])

    assert ids(findings) == ["a"]


def test_a_verdict_for_an_unknown_id_is_ignored() -> None:
    findings, summary = finalize_review([finding("a")], [verdict("ghost", "refuted")])

    assert ids(findings) == ["a"]
    assert "odrzucone" not in summary


def test_the_cap_keeps_the_most_severe_findings() -> None:
    validated = [finding(f"l{n}", "low") for n in range(4)] + [finding("h", "high")]

    findings, summary = finalize_review(validated, [], limit=3)

    assert ids(findings) == ["h", "l0", "l1"]
    assert "pominięte ponad limit 3: 2" in summary


def test_the_cap_counts_what_is_left_after_the_refuted_ones_are_dropped() -> None:
    validated = [finding("a", "high"), finding("b", "high"), finding("c", "low")]

    findings, _ = finalize_review(validated, [verdict("a", "refuted")], limit=2)

    assert ids(findings) == ["b", "c"]


def test_summary_counts_findings_by_severity() -> None:
    validated = [finding("1", "low"), finding("2", "high"), finding("3", "low")]

    _, summary = finalize_review(validated, [])

    assert summary == "Wg wagi: 1 high, 2 low"


def test_summary_says_how_many_findings_the_verifier_refuted() -> None:
    validated = [finding("a", "high"), finding("b", "medium")]

    findings, summary = finalize_review(validated, [verdict("a", "refuted")])

    assert ids(findings) == ["b"]
    assert summary == "Wg wagi: 1 medium; obalone przez weryfikatora i odrzucone: 1"


def test_summary_when_every_finding_was_refuted() -> None:
    findings, summary = finalize_review([finding("a", "high")], [verdict("a", "refuted")])

    assert findings == []
    assert summary == "Obalone przez weryfikatora i odrzucone: 1"


def test_the_inputs_are_not_changed() -> None:
    validated = [finding("l", "low"), finding("h", "high")]

    finalize_review(validated, [])

    assert ids(validated) == ["l", "h"]
