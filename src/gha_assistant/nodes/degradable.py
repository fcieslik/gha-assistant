from collections.abc import Callable
from typing import Any

from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from gha_assistant import agent


def compile_attempt(
    schema: type,
    attempt: Callable[..., Any],
    on_failure: Callable[[Any, Exception], dict[str, Any]],
    retry_policy: RetryPolicy,
    timeout: float,
) -> CompiledStateGraph:
    """One attempt of a node with a model, as a graph of its own that degrades instead of
    failing: the retry policy and the timeout apply to `attempt`, and once they are used
    up `on_failure(state, exc)` gives the update that stands in for the result.

    It is a nested graph because `add_node(error_handler=...)` does not work for a node
    that runs in a step with siblings (LangGraph 1.2.14 still re-raises the handled
    failure after the siblings finished; spike in ticket 06). `review_code`,
    `review_intent` and `verify_finding` all run in such a step. Alone in a step of the
    nested graph the attempt gets the retry, the timeout and the handler as intended.

    `on_failure` runs only for the failures `AGENT_RETRY` retries; a permanent one (a bad
    API key) is raised again, so the run fails with its own error instead of a Review
    that looks complete. Its warnings must name the exception type, never its message:
    warnings end up in the public comment.
    """

    def error_handler(state: Any, error: NodeError) -> dict[str, Any]:
        exc = error.error
        if not (isinstance(exc, Exception) and agent.is_transient_agent_error(exc)):
            raise exc
        return on_failure(state, exc)

    nested = StateGraph(schema)
    nested.add_node(
        "attempt", attempt, retry_policy=retry_policy, timeout=timeout, error_handler=error_handler
    )
    nested.add_edge(START, "attempt")
    nested.add_edge("attempt", END)
    return nested.compile()
