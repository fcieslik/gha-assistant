from typing import Any

import pytest

from gha_assistant.finding import Finding
from gha_assistant.nodes.validate_findings import check_findings

FILES = {"src/app.py": ["import os", "", "def run():", "    return os.getcwd()"]}


def finding(**fields: Any) -> Finding:
    base: dict[str, Any] = {"id": "code:1", "source": "code", "severity": "low", "message": "m"}
    return {**base, **fields}  # type: ignore[return-value]


def check(*candidates: Finding) -> tuple[list[Finding], list[str]]:
    return check_findings(list(candidates), code=set(FILES), read_lines=FILES.__getitem__)


def test_anchored_finding_with_a_matching_quote_passes() -> None:
    f = finding(file="src/app.py", line=4, evidence="return os.getcwd()")

    assert check(f) == ([f], [])


def test_finding_without_evidence_passes_when_its_line_exists() -> None:
    f = finding(file="src/app.py", line=1)

    assert check(f) == ([f], [])


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        pytest.param(
            {"file": "src/ghost.py", "line": 1, "evidence": "import os"},
            "src/ghost.py",
            id="file outside the change",
        ),
        pytest.param({"file": "src/app.py", "line": 5}, "linia 5", id="line past the file"),
        pytest.param({"file": "src/app.py", "line": 0}, "linia 0", id="line before the file"),
        pytest.param(
            {"file": "src/app.py", "line": 3, "evidence": "import os"},
            "src/app.py:3",
            id="quote not on that line",
        ),
        pytest.param({"source": "spec"}, "spec_ref", id="spec without spec_ref"),
        pytest.param({"source": "spec", "file": "src/app.py"}, "spec_ref", id="anchored spec"),
        pytest.param({}, "spec_ref", id="general remark without spec_ref"),
        pytest.param({"line": 1}, "bez pliku", id="line without a file"),
    ],
)
def test_finding_that_points_nowhere_is_rejected_with_its_reason(
    fields: dict[str, Any], reason: str
) -> None:
    validated, warnings = check(finding(**fields))

    assert validated == []
    (warning,) = warnings
    assert "code:1" in warning
    assert reason in warning


def test_general_remark_with_spec_ref_passes() -> None:
    f = finding(source="spec", spec_ref=".scratch/x/spec.md: criterion 2")

    assert check(f) == ([f], [])


def test_file_without_line_passes_when_the_file_is_in_the_change() -> None:
    f = finding(source="spec", file="src/app.py", spec_ref="spec.md")

    assert check(f) == ([f], [])


def test_exact_duplicate_is_dropped_and_the_most_severe_is_kept() -> None:
    low = finding(id="a", file="src/app.py", line=1, severity="low")
    high = finding(id="b", file="src/app.py", line=1, severity="high", message="other")

    validated, warnings = check(low, high)

    assert validated == [high]
    assert len(warnings) == 1
    assert "a" in warnings[0]


def test_same_line_from_another_source_is_not_a_duplicate() -> None:
    code = finding(id="a", file="src/app.py", line=1)
    spec = finding(id="b", source="spec", file="src/app.py", line=1, spec_ref="spec.md")

    assert check(code, spec) == ([code, spec], [])


def test_other_line_is_not_a_duplicate() -> None:
    first = finding(id="a", file="src/app.py", line=1)
    second = finding(id="b", file="src/app.py", line=2)

    assert check(first, second) == ([first, second], [])


def test_two_different_general_remarks_are_not_duplicates() -> None:
    first = finding(id="a", source="spec", spec_ref="spec.md#1", message="criterion 1 missing")
    second = finding(id="b", source="spec", spec_ref="spec.md#2", message="criterion 2 missing")

    assert check(first, second) == ([first, second], [])


def test_unreadable_file_has_no_lines() -> None:
    def missing(_path: str) -> list[str]:
        return []

    f = finding(file="src/app.py", line=1)

    validated, warnings = check_findings([f], code={"src/app.py"}, read_lines=missing)

    assert validated == []
    assert "linia 1" in warnings[0]
