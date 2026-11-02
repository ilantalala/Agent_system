from dataclasses import dataclass, field
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage
from langchain_core.tools import BaseTool
from langgraph.graph.message import add_messages
from langgraph.managed import RemainingSteps



class RuntimeState(TypedDict):
    # The only thing the checkpointer saves per thread: the conversation,
    # including AI tool calls and the ToolMessages that answer them.
    messages: Annotated[list[AnyMessage], add_messages]
    # Filled in by LangGraph before each node runs (recursion_limit minus steps
    # used). Read-only for us and never saved by the checkpointer.
    remaining_steps: RemainingSteps


@dataclass
class RuntimeContext:
    # Per-run inputs that must never be checkpointed: the model holds the
    # owner's API key, and the prompt/tools come fresh from the agent
    # definition each turn.
    model: BaseChatModel
    system_prompt: str
    tools: list[BaseTool] = field(default_factory=list)
    
