from app.llm import LLMMessage, ToolSchema, call_llm
from app.schemas import DraftReview

REVIEWER_SYSTEM_PROMPT = (
    "You are a strict reviewer judging a draft system prompt for an AI "
    "agent against a fixed rubric. Evaluate the draft on exactly five "
    "dimensions: role_clarity, tasks, tone, edge_cases, examples.\n\n"
    "For each dimension, decide whether the draft passes or fails, and "
    "write a short note explaining why — if it fails, the note should say "
    "specifically what is missing or unclear.\n\n"
    "Do not reply in prose. Call the submit_review tool with your verdict "
    "for all five dimensions."
)

_REVIEW_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "passed": {
            "type": "boolean",
            "description": "Whether the draft satisfies this dimension.",
        },
        "note": {
            "type": "string",
            "description": "Why it passed or failed, and what's missing if it failed.",
        },
    },
    "required": ["passed", "note"],
}

SUBMIT_REVIEW_TOOL = ToolSchema(
    name="submit_review",
    description="Submit your rubric verdict for the draft system prompt.",
    input_schema={
        "type": "object",
        "properties": {
            "role_clarity": _REVIEW_ITEM_SCHEMA,
            "tasks": _REVIEW_ITEM_SCHEMA,
            "tone": _REVIEW_ITEM_SCHEMA,
            "edge_cases": _REVIEW_ITEM_SCHEMA,
            "examples": _REVIEW_ITEM_SCHEMA,
        },
        "required": ["role_clarity", "tasks", "tone", "edge_cases", "examples"],
    },
)


def review_draft(draft_system_prompt: str) -> DraftReview:
    
    response = call_llm(
        REVIEWER_SYSTEM_PROMPT,
        [LLMMessage(role="user", content=draft_system_prompt)],
        tools=[SUBMIT_REVIEW_TOOL],
    )
    if response.tool_call is None or response.tool_call.name != "submit_review":
        raise ValueError("reviewer did not call submit_review")
    return DraftReview.model_validate(response.tool_call.arguments)
