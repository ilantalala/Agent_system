from langchain_core.messages import SystemMessage,AIMessage
from langgraph.runtime import Runtime

from app.runtime.state import RuntimeContext, RuntimeState
STEP_LIMIT_MESSAGE = (
    "Sorry, I couldn't finish that within my step limit. "
    "Could you try asking in a simpler way?"
)



async def agent(state: RuntimeState, runtime: Runtime[RuntimeContext]) -> dict:
    ctx = runtime.context
    # Some providers reject an empty tools list, so only bind when there are tools.
    model = ctx.model.bind_tools(ctx.tools) if ctx.tools else ctx.model
    # The system prompt is prepended on every call, never stored in state, so
    # editing an agent's prompt takes effect on the very next turn.
    reply = await model.ainvoke([SystemMessage(ctx.system_prompt), *state["messages"]])
    # Wants tools but there's no room left for "tools" + another "agent" step:
    # answer now, so the thread never ends on an unanswered tool call.
    if reply.tool_calls and state["remaining_steps"] < 2:
        return {"messages": [AIMessage(STEP_LIMIT_MESSAGE)]}
    return {"messages": [reply]}

