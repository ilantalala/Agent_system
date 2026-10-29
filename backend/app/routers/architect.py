from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.builder.graph import builder_thread_id
from app.builder.state import BuilderContext
from app.database import get_db
from app.dependencies import get_owned_agent
from app.llm.chat_model import get_chat_model
from app.models import Agent, Conversation
from app.orchestrator import save_turn
from app.schemas import ArchitectChatRequest, ArchitectChatResponse, ChatMessage

router = APIRouter(prefix="/agents/{agent_id}/architect", tags=["architect"])


# The DB layer is still synchronous, so DB work runs in a worker thread and
# only the slow part — the graph's model calls — runs on the event loop.
def _start_turn(db: Session, agent: Agent) -> tuple[int, BaseChatModel]:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.agent_id == agent.id, Conversation.kind == "architect"
            )
    )
    if conversation is None:
        conversation = Conversation(agent_id=agent.id, kind = "architect")
        db.add(conversation)
        db.commit()  # don't hold a transaction open across the model calls
    return conversation.id, get_chat_model(agent, agent.owner)


def _finish_turn(
    db: Session, agent: Agent, conversation_id: int, user_content: str, state: dict
) -> ArchitectChatResponse:
    reply_text = state["messages"][-1].text
    if state.get("draft") is not None:
        agent.draft_system_prompt = state["draft"]
        agent.draft_review = state.get("review")
    conversation = db.get(Conversation, conversation_id)
    save_turn(db, conversation, user_content, reply_text)
    response = ArchitectChatResponse(
        message=ChatMessage(role="assistant", content=reply_text),
        draft_system_prompt=agent.draft_system_prompt,
        draft_review=agent.draft_review,
    )
    db.commit()
    return response


@router.post("/chat", response_model=ArchitectChatResponse)
async def architect_chat(
    payload: ArchitectChatRequest,
    request: Request,
    agent: Agent = Depends(get_owned_agent),
    db: Session = Depends(get_db),
):
    conversation_id, model = await run_in_threadpool(_start_turn, db, agent)

    # One graph run per user message; the checkpointer loads and saves the
    # builder's state for this conversation's thread.
    state = await request.app.state.builder_graph.ainvoke(
        {"messages": [HumanMessage(payload.content)]},
        config={"configurable": {"thread_id": builder_thread_id(conversation_id)}},
        context=BuilderContext(model=model),
    )

    return await run_in_threadpool(
        _finish_turn, db, agent, conversation_id, payload.content, state
    )
