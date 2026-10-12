from typing import Literal, NotRequired, TypedDict

Severity = Literal["low", "medium", "high"]
Source = Literal["spec", "code"]
VerdictKind = Literal["confirmed", "refuted", "inconclusive"]


class Finding(TypedDict):
    """One remark about the PR, in the same shape at every stage of the graph.

    A Finding without `file` and `line` is a general remark (e.g. an unmet criterion):
    it goes to the summary, not to a line comment.
    """

    id: str  # assigned by code, never by the model
    source: Source  # set by the node, never by the model
    severity: Severity
    message: str
    file: NotRequired[str]
    line: NotRequired[int]
    evidence: NotRequired[str]  # verbatim quote from the code
    suggestion: NotRequired[str]
    spec_ref: NotRequired[str]  # Intent file and criterion; required when source is "spec"


class Verdict(TypedDict):
    finding_id: str
    verdict: VerdictKind
    reason: str
