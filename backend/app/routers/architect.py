from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.reviewer import review_draft
from app.database import get_db
from app.dependencies import get_owned_agent
from app.llm import LLMMessage, ToolSchema, call_llm
from app.models import Agent, Conversation, Message
from app.orchestrator import run_agent_turn, save_turn
from app.schemas import ArchitectChatRequest, ArchitectChatResponse, ChatMessage
import logging

logger = logging.getLogger(__name__)

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

FEEDBACK_SYSTEM_PROMPT_TEMPLATE = (
    "{base}\n\n"
    "You just proposed a draft system prompt, but a review found it still "
    "needs work on:\n{gaps}\n\n"
    "Ask ONE natural follow-up question that addresses the first item above. "
    "Continue the interview as if it's simply the next question — do not "
    "mention 'review', 'rubric', or that an evaluation happened."
)

DRAFT_READY_MESSAGE = (
    "Your draft passed review on all five fronts — role, tasks, tone, edge "
    "cases, and examples are all covered. It's ready to move to testing."
)

def _next_question_from_review(
    conversation: Conversation, db: Session, user_content: str, failed: list[tuple[str, str]]
) -> str:
    gaps = "\n".join(f"- {dimension}: {note}" for dimension, note in failed)
    system_prompt = FEEDBACK_SYSTEM_PROMPT_TEMPLATE.format(
        base=ARCHITECT_SYSTEM_PROMPT, gaps=gaps
    )
    response = run_agent_turn(db, conversation, system_prompt, user_content)
    return response.text

@router.post("/chat", response_model=ArchitectChatResponse)
def architect_chat(
    payload: ArchitectChatRequest,
    agent: Agent = Depends(get_owned_agent),
    db: Session = Depends(get_db),
):
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.agent_id == agent.id, Conversation.kind == "architect"
            )
    )
    if conversation is None:
        conversation = Conversation(agent_id=agent.id, kind = "architect")
        db.add(conversation)
        db.flush()

    
    response = run_agent_turn(
        db, conversation, ARCHITECT_SYSTEM_PROMPT, payload.content, tools=[PROPOSE_DRAFT_TOOL]
    )

    if response.tool_call is not None and response.tool_call.name == "propose_draft":
        agent.draft_system_prompt = response.tool_call.arguments["system_prompt"]
        try:
            review = review_draft(agent.draft_system_prompt)
            agent.draft_review = review.model_dump()
        except Exception:
            logger.warning("reviewer failed for agent %s", agent.id, exc_info=True)
            agent.draft_review = None

        failed = [
            (dimension, item["note"])
            for dimension, item in (agent.draft_review or {}).items()
            if not item["passed"]
        ]
        if failed:
            reply_text = _next_question_from_review(conversation, db, payload.content, failed)
        elif agent.draft_review is not None:
            reply_text = DRAFT_READY_MESSAGE
        else:
            reply_text = DRAFT_PROPOSED_MESSAGE

    else:
        reply_text = response.text

    save_turn(db, conversation, payload.content, reply_text)
    db.commit()

    return ArchitectChatResponse(
        message=ChatMessage(role="assistant", content=reply_text),
        draft_system_prompt=agent.draft_system_prompt,
        draft_review=agent.draft_review,
    )
