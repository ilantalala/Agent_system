from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.chat_model import get_chat_model
from app.models import Conversation, Message

def load_history(db: Session, conversation: Conversation) -> list[BaseMessage]:
    history = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.id)

    ).all()
    return [
        HumanMessage(m.content) if m.role == "user" else AIMessage(m.content)
        for m in history
    ]

def run_agent_turn(
    db: Session,
    conversation: Conversation,
    system_prompt: str,
    user_content: str,
) -> AIMessage:
    agent = conversation.agent
    # BYOK: the agent's owner pays, even when an admin is the one chatting.
    model = get_chat_model(agent, agent.owner)
    llm_messages = [SystemMessage(system_prompt), *load_history(db, conversation)]
    llm_messages.append(HumanMessage(user_content))
    return model.invoke(llm_messages)

def save_turn(
    db: Session, conversation: Conversation, user_content: str, reply_text: str
) -> None:
    db.add(Message(conversation_id=conversation.id, role="user", content=user_content))
    db.add(Message(conversation_id=conversation.id, role="assistant", content=reply_text))
