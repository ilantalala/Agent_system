from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from app.config import settings
from app.models import Agent, User


def _resolve_api_key(user_key: str | None, env_key: str | None, provider: str) -> str:
    # BYOK: the user's own key pays for their calls. The .env key is only a
    # development fallback, so production never bills our account.
    if user_key:
        return user_key
    if settings.environment == "development" and env_key:
        return env_key
    raise RuntimeError(
        f"No {provider} API key: the user has none stored"
        + ("" if settings.environment == "development" else " (no .env fallback outside development)")
    )


def get_chat_model(agent: Agent, user: User) -> BaseChatModel:
    # agent is unused for now: it will choose the model later.
    if settings.llm_provider == "openai":
        return init_chat_model(
            settings.openai_model,
            model_provider="openai",
            api_key=_resolve_api_key(user.openai_api_key, settings.openai_api_key, "OpenAI"),
            max_tokens=settings.openai_max_output_tokens,
        )

    if settings.llm_provider == "anthropic":
        return init_chat_model(
            settings.anthropic_model,
            model_provider="anthropic",
            api_key=_resolve_api_key(
                user.anthropic_api_key, settings.anthropic_api_key, "Anthropic"
            ),
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
