from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from app.runtime.events import DoneEvent, RunEvent, TokenEvent, ToolCallEvent, ToolResultEvent
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
        reply: str | None = None
        async for event in self.stream(definition, thread_id, message):
            if isinstance(event, DoneEvent):
                reply = event.reply
        if reply is None:
            raise RuntimeError("Agent stream ended without a reply")
        return reply

    async def stream(
        self, definition: AgentDefinition, thread_id: str, message: str
    ) -> AsyncIterator[RunEvent]:
        graph = build_runtime_graph(definition.tools, self._checkpointer)
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": self._recursion_limit,
        }
        context = RuntimeContext(
            model=definition.model,
            system_prompt=definition.system_prompt,
            tools=definition.tools,
        )
        checkpoint_tuple = await self._checkpointer.aget_tuple(config)
        history = (
            checkpoint_tuple.checkpoint["channel_values"].get("messages", [])
            if checkpoint_tuple is not None else []
        )
        inputs: list[ToolMessage | HumanMessage] = []
        # Pending writes from an interrupted step are discarded by the next run,
        # so only committed messages can need an answer before another user turn.
        if history and isinstance(history[-1], AIMessage):
            inputs.extend(
                ToolMessage(
                    content="Interrupted before this tool ran.",
                    tool_call_id=call["id"],
                    name=call["name"],
                    status="error",
                )
                for call in history[-1].tool_calls
            )
        inputs.append(HumanMessage(message))
        reply = ""
        async for mode, payload in graph.astream(
            {"messages": inputs}, config, context=context,
            stream_mode=["messages", "updates"],
        ):
            if mode == "messages":
                item, metadata = payload
                if metadata.get("langgraph_node") == "agent" and isinstance(
                    item, (AIMessageChunk, AIMessage)
                ):
                    if item.text:
                        yield TokenEvent(text=item.text)
                elif metadata.get("langgraph_node") == "tools" and isinstance(item, ToolMessage):
                    yield ToolResultEvent(
                        id=item.tool_call_id, name=item.name or "", content=item.text,
                        is_error=item.status == "error",
                    )
            elif mode == "updates":
                for item in payload.get("agent", {}).get("messages", []):
                    if isinstance(item, AIMessage):
                        reply = item.text
                        for call in item.tool_calls:
                            yield ToolCallEvent(id=call["id"], name=call["name"], args=call["args"])
        yield DoneEvent(reply=reply)
