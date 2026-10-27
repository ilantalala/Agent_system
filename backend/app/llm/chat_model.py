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
    
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set in .env"
            )
        return init_chat_model(
            settings.anthropic_model,
            model_provider="anthropic",
            api_key=settings.anthropic_api_key,
            max_tokens=settings.anthropic_max_tokens,
        )
        
    if settings.llm_provider == "ollama":
        return init_chat_model(
            settings.ollama_model,
            model_provider="ollama",
            base_url=settings.ollama_base_url,
            client_kwargs={"timeout": settings.ollama_timeout_seconds},
        )

    raise ValueError(
        f"Unknown LLM_PROVIDER {settings.llm_provider!r}. "
        "Known: anthropic, ollama, openai"
    )

