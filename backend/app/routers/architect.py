from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_agent
from app.llm import LLMMessage, ToolSchema, call_llm
from app.models import Agent, Conversation, Message
from app.schemas import ArchitectChatRequest, ArchitectChatResponse, ChatMessage

router = APIRouter(prefix="/agents/{agent_id}/architect", tags=["architect"])

PROPOSE_DRAFT_TOOL = ToolSchema(
    name="propose_draft",
    description=(
        "Call this once you have enough information about the agent's "
        "role, tasks, tone, edge cases, and an example interaction to "
        "propose a complete system prompt."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "system_prompt": {
                "type": "string",
                "description": (
                    "The complete system prompt drafted for the new agent, "
                    "based on everything learned in the interview."
                ),
            }
        },
        "required": ["system_prompt"],
    },
)

DRAFT_PROPOSED_MESSAGE = (
    "I've put together a draft system prompt for your agent based on our "
    "conversation. Check it out, and let me know if you'd like any changes."
)

ARCHITECT_SYSTEM_PROMPT = (
    "You are an interviewer helping a user design a system prompt for a "
    "new AI agent they want to build.\n\n"
    "Ask exactly ONE focused question per reply. Never ask more than one "
    "question in a single message.\n\n"
    "Over the course of the conversation, work through these topics, one "
    "at a time, in whatever order fits the conversation:\n"
    "- the agent's role and purpose\n"
    "- the main tasks it should handle\n"
    "- its tone and personality\n"
    "- edge cases or situations it should handle carefully\n"
    "- an example of a typical interaction\n\n"
    "Before asking your next question, briefly acknowledge what the user "
    "just told you in a sentence or less, so it reads as a conversation, "
    "not a form. Keep every message short.\n\n"
    "Once you have learned enough about all of the topics above, call the "
    "propose_draft tool with the complete system prompt instead of asking "
    "another question."
)


@router.post("/chat", response_model=ArchitectChatResponse)
def architect_chat(
    payload: ArchitectChatRequest,
    agent: Agent = Depends(get_owned_agent),
    db: Session = Depends(get_db),
):
    conversation = db.scalar(
        select(Conversation).where(Conversation.agent_id == agent.id)
    )
    if conversation is None:
        conversation = Conversation(agent_id=agent.id)
        db.add(conversation)
        db.flush()

    history = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.id)
    ).all()
    llm_messages = [LLMMessage(role=m.role, content=m.content) for m in history]
    llm_messages.append(LLMMessage(role="user", content=payload.content))

    response = call_llm(
        ARCHITECT_SYSTEM_PROMPT, llm_messages, tools=[PROPOSE_DRAFT_TOOL]
    )

    if response.tool_call is not None and response.tool_call.name == "propose_draft":
        agent.draft_system_prompt = response.tool_call.arguments["system_prompt"]
        reply_text = DRAFT_PROPOSED_MESSAGE
    else:
        reply_text = response.text

    db.add(Message(conversation_id=conversation.id, role="user", content=payload.content))
    db.add(Message(conversation_id=conversation.id, role="assistant", content=reply_text))
    db.commit()

    return ArchitectChatResponse(
        message=ChatMessage(role="assistant", content=reply_text),
        draft_system_prompt=agent.draft_system_prompt,
    )
