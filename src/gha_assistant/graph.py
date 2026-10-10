from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from gha_assistant.nodes.collect_input import collect_input
from gha_assistant.nodes.publish import publish
from gha_assistant.nodes.run_agent import run_agent
from gha_assistant.state import ReviewState


def build_graph() -> CompiledStateGraph:
    builder = StateGraph(ReviewState)
    builder.add_node("collect_input", collect_input)
    builder.add_node("run_agent", run_agent)
    builder.add_node("publish", publish)
    builder.add_edge(START, "collect_input")
    builder.add_edge("collect_input", "run_agent")
    builder.add_edge("run_agent", "publish")
    builder.add_edge("publish", END)
    return builder.compile()
