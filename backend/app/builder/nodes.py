import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END
from langgraph.runtime import Runtime

from app.builder.prompts import (
    ARCHITECT_SYSTEM_PROMPT,
    DRAFT_PROPOSED_MESSAGE,
    DRAFT_READY_MESSAGE,
    FEEDBACK_SYSTEM_PROMPT_TEMPLATE,
    PROPOSE_DRAFT_TOOL,
    REVIEWER_SYSTEM_PROMPT,
)
from app.builder.state import BuilderContext, BuilderState
from app.llm.structured import get_tool_call, invoke_structured
from app.schemas import DraftReview

logger = logging.getLogger(__name__)


def failed_dimensions(review: dict | None) -> list[tuple[str, str]]:
    return [
        (dimension, item["note"])
        for dimension, item in (review or {}).items()
        if not item["passed"]
    ]


async def architect(state: BuilderState, runtime: Runtime[BuilderContext]) -> dict:
    model = runtime.context.model

    # Coming straight from the reviewer with gaps: ask one follow-up question
    # that targets them. No tool here, so it can't propose again this turn.
    gaps = failed_dimensions(state.get("review")) if state.get("status") == "reviewing" else []
    if gaps:
        system_prompt = FEEDBACK_SYSTEM_PROMPT_TEMPLATE.format(
            base=ARCHITECT_SYSTEM_PROMPT,
            gaps="\n".join(f"- {dimension}: {note}" for dimension, note in gaps),
        )
        reply = await model.ainvoke([SystemMessage(system_prompt), *state["messages"]])
        return {"messages": [reply], "status": "interviewing"}

    reply = await model.bind_tools([PROPOSE_DRAFT_TOOL]).ainvoke(
        [SystemMessage(ARCHITECT_SYSTEM_PROMPT), *state["messages"]]
    )
    update: dict = {"messages": [reply]}
    tool_call = get_tool_call(reply, "propose_draft")
    if tool_call is not None and tool_call["name"] == "propose_draft":
        update["draft"] = tool_call["args"]["system_prompt"]
        update["status"] = "reviewing"
    return update


async def reviewer(state: BuilderState, runtime: Runtime[BuilderContext]) -> dict:
    # Every native tool call must be answered by a ToolMessage, or providers
    # reject the history on the next turn.
    last = state["messages"][-1]
    acks = [
        ToolMessage("Draft received.", tool_call_id=tool_call["id"])
        for tool_call in getattr(last, "tool_calls", [])
        if tool_call.get("id")
    ]
    try:
        review = await invoke_structured(
            runtime.context.model,
            DraftReview,
            [SystemMessage(REVIEWER_SYSTEM_PROMPT), HumanMessage(state["draft"])],
        )
    except Exception:
        logger.warning("reviewer failed", exc_info=True)
        return {
            "messages": [*acks, AIMessage(DRAFT_PROPOSED_MESSAGE)],
            "review": None,
            "status": "interviewing",
        }
    return {"messages": acks, "review": review.model_dump()}


async def mark_ready(state: BuilderState) -> dict:
    return {"messages": [AIMessage(DRAFT_READY_MESSAGE)], "status": "ready"}


def route_after_architect(state: BuilderState) -> str:
    return "reviewer" if state.get("status") == "reviewing" else END


def route_after_reviewer(state: BuilderState) -> str:
    if state.get("review") is None:
        return END  # reviewer failed; DRAFT_PROPOSED_MESSAGE already added
    if failed_dimensions(state["review"]):
        return "architect"
    return "mark_ready"
