from sqlalchemy.orm import Session

from app.models import Conversation, Message


def save_turn(
    db: Session, conversation: Conversation, user_content: str, reply_text: str
) -> None:
    db.add(Message(conversation_id=conversation.id, role="user", content=user_content))
    db.add(Message(conversation_id=conversation.id, role="assistant", content=reply_text))
