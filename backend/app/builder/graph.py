from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.builder.nodes import (
    architect,
    mark_ready,
    reviewer,
    route_after_architect,
    route_after_reviewer,
)
from app.builder.state import BuilderContext, BuilderState
from app.config import settings


def build_builder_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    graph = StateGraph(BuilderState, context_schema=BuilderContext)
    graph.add_node("architect", architect)
    graph.add_node("reviewer", reviewer)
    graph.add_node("mark_ready", mark_ready)

    graph.add_edge(START, "architect")
    graph.add_conditional_edges("architect", route_after_architect, ["reviewer", END])
    # The evaluator-optimizer loop: gaps go back to the architect.
    graph.add_conditional_edges(
        "reviewer", route_after_reviewer, ["architect", "mark_ready", END]
    )
    graph.add_edge("mark_ready", END)
    return graph.compile(checkpointer=checkpointer)


def checkpointer_conn_string() -> str:
    # SQLAlchemy needs the "+psycopg" driver hint; psycopg itself doesn't.
    return settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def builder_thread_id(conversation_id: int) -> str:
    return f"builder:{conversation_id}"
