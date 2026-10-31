from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class BuilderState(TypedDict):
    # Reducer: add_messages appends new messages (and replaces ones with the
    # same id) instead of overwriting the whole list.
    messages: Annotated[list[AnyMessage], add_messages]
    # No reducer: a node's value simply overwrites the old one.
    draft: str | None
    review: dict | None
    status: Literal["interviewing", "reviewing", "ready"]


@dataclass
class BuilderContext:
    # Objects a run needs but that must never be saved by the checkpointer
    # (the model holds the owner's API key).
    model: BaseChatModel
