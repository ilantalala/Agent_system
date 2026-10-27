from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.config import settings
from app.models import Agent, User


def get_chat_model(agent: Agent, user: User) -> BaseChatModel:
    # agent and user are unused for now: agent will choose the model later,
    # and user will supply the API key in Story 3 (BYOK).
    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set in .env"
            )
        return init_chat_model(
            settings.openai_model,
            model_provider="openai",
            api_key=settings.openai_api_key,
            max_tokens=settings.openai_max_output_tokens,
        )
    raise ValueError(
        f"get_chat_model doesn't support LLM_PROVIDER {settings.llm_provider!r} yet"
    )
