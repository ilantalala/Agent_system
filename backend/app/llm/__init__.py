from app.config import settings
from app.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolCall, ToolSchema
from app.llm.fake import FakeProvider
from app.llm.openai_provider import OpenAIProvider
from app.llm.ollama_provider import OllamaProvider 
from app.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    StructuredOutputError,
    ToolCall,
    ToolSchema,
)
_PROVIDERS: dict[str, type[LLMProvider]] = {
    "fake": FakeProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}

def get_provider() -> LLMProvider:
    try:
        provider_cls = _PROVIDERS[settings.llm_provider]
    except KeyError:
        known = ", ".join(sorted(_PROVIDERS))
        raise ValueError(
            f"Unknown LLM_PROVIDER {settings.llm_provider!r}. Known: {known}"
            )
    return provider_cls()    

def call_llm(
    system_prompt: str,
    messages: list[LLMMessage],
    tools: list[ToolSchema] | None = None,
) -> LLMResponse:
    return get_provider().complete(system_prompt, messages, tools)