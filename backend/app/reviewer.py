from langchain_core.messages import HumanMessage, SystemMessage

from app.llm.chat_model import get_chat_model
from app.llm.structured import invoke_structured
from app.models import Agent
from app.schemas import DraftReview

REVIEWER_SYSTEM_PROMPT = (
    "You are a strict reviewer judging a draft system prompt for an AI "
    "agent against a fixed rubric. Evaluate the draft on exactly five "
    "dimensions: role_clarity, tasks, tone, edge_cases, examples.\n\n"
    "For each dimension, decide whether the draft passes or fails, and "
    "write a short note explaining why — if it fails, the note should say "
    "specifically what is missing or unclear.\n\n"
    "Do not reply in prose. Return your verdict for all five dimensions."
)


def review_draft(agent: Agent, draft_system_prompt: str) -> DraftReview:
    model = get_chat_model(agent, agent.owner)
    return invoke_structured(
        model,
        DraftReview,
        [SystemMessage(REVIEWER_SYSTEM_PROMPT), HumanMessage(draft_system_prompt)],
    )
