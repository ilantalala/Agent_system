from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from app.runtime.graph import build_runtime_graph
from app.runtime.state import RuntimeContext
# Tool rounds allowed per user message (each round = one paid model call).
MAX_TOOL_ROUNDS = 5



@dataclass
class AgentDefinition:
    # Everything needed to run an agent, already chosen by the caller
    # (e.g. draft vs approved prompt). The model carries the payer's API key.
    system_prompt: str
    model: BaseChatModel
    tools: list[BaseTool] = field(default_factory=list)


class AgentRunner:
    # The only entry point to the runtime: callers never import LangGraph.
    def __init__(
        self,
        checkpointer: BaseCheckpointSaver | None = None,
        max_tool_rounds: int = MAX_TOOL_ROUNDS,
    ):
        # The app passes its long-lived Postgres checkpointer; scripts can
        # omit it and get one that forgets everything on exit.
        self._checkpointer = checkpointer or InMemorySaver()
        # LangGraph counts writing the input as a step too: N rounds of
        # agent+tools plus the final agent answer need 2N + 2.
        self._recursion_limit = 2 * max_tool_rounds + 2
        
    async def run(self, definition: AgentDefinition, thread_id: str, message: str) -> str:
        graph = build_runtime_graph(definition.tools, self._checkpointer)
        context = RuntimeContext(
            model=definition.model,
            system_prompt=definition.system_prompt,
            tools=definition.tools,
        )
        # Send only the new message: the checkpointer loads the thread's history.
        state = await graph.ainvoke(
            {"messages": [HumanMessage(message)]},
            {"configurable": {"thread_id": thread_id}, "recursion_limit": self._recursion_limit},
            context=context,
        )
        return state["messages"][-1].text
