from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.runtime.nodes import agent
from app.runtime.state import RuntimeContext, RuntimeState


def build_runtime_graph(
    tools: list[BaseTool], checkpointer: BaseCheckpointSaver | None = None
) -> CompiledStateGraph:
    # Compiled per run: ToolNode needs this agent's tools at build time, and
    # different agents have different tools. Compiling is cheap (no I/O).
    graph = StateGraph(RuntimeState, context_schema=RuntimeContext)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools))

    graph.add_edge(START, "agent")
    # The tool-calling loop: tool calls go to "tools", a plain answer ends the run.
    graph.add_conditional_edges("agent", tools_condition, ["tools", "__end__"])
    graph.add_edge("tools", "agent")
    return graph.compile(checkpointer=checkpointer)
