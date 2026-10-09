from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm import LLMMessage, LLMResponse, ToolSchema, call_llm
from app.models import Conversation, Message

def load_history(db: Session, conversation: Conversation) -> list[LLMMessage]:
    history = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.id)

    ).all()
    return [LLMMessage(role=m.role, content=m.content) for m in history]

def run_agent_turn(
    db: Session,
    conversation: Conversation,
    system_prompt: str,
    user_content: str,
    tools: list[ToolSchema] | None = None,
) -> LLMResponse:
    llm_messages = load_history(db,conversation)
    llm_messages.append(LLMMessage(role="user", content=user_content))
    return call_llm(system_prompt, llm_messages, tools=tools)

def save_turn(
    db: Session, conversation: Conversation, user_content: str, reply_text: str
) -> None:
    db.add(Message(conversation_id=conversation.id, role="user", content=user_content))
    db.add(Message(conversation_id=conversation.id, role="assistant", content=reply_text))