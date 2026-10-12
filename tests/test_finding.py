from gha_assistant.finding import Finding, Verdict


def test_finding_has_the_agreed_shape() -> None:
    assert set(Finding.__annotations__) == {
        "id",
        "source",
        "severity",
        "message",
        "file",
        "line",
        "evidence",
        "suggestion",
        "spec_ref",
    }
    # A Finding without file and line is a general remark, so those stay optional.
    assert Finding.__required_keys__ == {"id", "source", "severity", "message"}


def test_verdict_refers_to_a_finding_by_id() -> None:
    assert set(Verdict.__annotations__) == {"finding_id", "verdict", "reason"}
