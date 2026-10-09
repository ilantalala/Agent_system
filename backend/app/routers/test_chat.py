from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_agent
from app.models import Agent, Conversation
from app.orchestrator import run_agent_turn, save_turn
from app.schemas import ChatMessage, TestChatRequest, TestChatResponse

router = APIRouter(prefix="/agents/{agent_id}/test-chat", tags=["test-chat"])


@router.post("/chat", response_model=TestChatResponse)
def test_chat(
    payload: TestChatRequest,
    agent: Agent = Depends(get_owned_agent),
    db: Session = Depends(get_db),
):
    if agent.draft_system_prompt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent has no draft system prompt to test yet",
        )

    conversation = db.scalar(
        select(Conversation).where(
            Conversation.agent_id == agent.id, Conversation.kind == "test"
        )
    )
    if conversation is None:
        conversation = Conversation(agent_id=agent.id, kind="test")
        db.add(conversation)
        db.flush()

    response = run_agent_turn(db, conversation, agent.draft_system_prompt, payload.content)
    reply_text = response.text

    save_turn(db, conversation, payload.content, reply_text)
    db.commit()

    return TestChatResponse(message=ChatMessage(role="assistant", content=reply_text))
