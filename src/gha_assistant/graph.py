from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from gha_assistant.agent import AGENT_RETRY, NODE_TIMEOUT_SECONDS
from gha_assistant.github_io import GITHUB_RETRY
from gha_assistant.nodes.collect_input import COLLECT_INPUT_RETRY, collect_input
from gha_assistant.nodes.judge_findings import judge_findings
from gha_assistant.nodes.nothing_to_review import nothing_to_review
from gha_assistant.nodes.publish import publish
from gha_assistant.nodes.review_code import review_code
from gha_assistant.nodes.review_intent import review_intent
from gha_assistant.nodes.validate_findings import route_after_validation, validate_findings
from gha_assistant.nodes.verify_finding import verify_finding
from gha_assistant.state import ReviewState

# Upper bound on nodes running at once; `Send` workers are what hit it.
MAX_CONCURRENCY = 5


def build_graph() -> CompiledStateGraph:
    builder = StateGraph(ReviewState)
    builder.add_node("collect_input", collect_input, retry_policy=COLLECT_INPUT_RETRY)
    builder.add_node(
        "review_code", review_code, retry_policy=AGENT_RETRY, timeout=NODE_TIMEOUT_SECONDS
    )
    builder.add_node("review_intent", review_intent)
    builder.add_node("validate_findings", validate_findings)
    builder.add_node("verify_finding", verify_finding)
    builder.add_node("judge_findings", judge_findings)
    builder.add_node("publish", publish, retry_policy=GITHUB_RETRY)
    builder.add_node("nothing_to_review", nothing_to_review, retry_policy=GITHUB_RETRY)

    builder.add_edge(START, "collect_input")
    # collect_input routes itself with Command (review_code via Send, review_intent,
    # nothing_to_review); an edge out of it would run in addition to the Command.
    #
    # Fan-in: one edge per reviewer rather than one edge with a list of sources. A list
    # is a barrier that waits for every source, and review_intent is skipped when there
    # are no Intent files, so the barrier would never open. The reviewers run in the
    # same step, so validate_findings still runs once, after all of them.
    builder.add_edge("review_code", "validate_findings")
    builder.add_edge("review_intent", "validate_findings")
    # No Findings goes straight to publish; otherwise one verify_finding per Finding.
    builder.add_conditional_edges(
        "validate_findings", route_after_validation, ["verify_finding", "publish"]
    )
    builder.add_edge("verify_finding", "judge_findings")
    builder.add_edge("judge_findings", "publish")
    builder.add_edge("publish", END)
    builder.add_edge("nothing_to_review", END)
    return builder.compile().with_config(max_concurrency=MAX_CONCURRENCY)
