import json
import logging
from openai import OpenAI

from app.config import settings
from app.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolCall, ToolSchema
from app.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    StructuredOutputError,
    ToolCall,
    ToolSchema,
)
logger= logging.getLogger(__name__)

class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set in .env"
            )
        self._client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self._max_tokens = settings.openai_max_output_tokens

    def _to_openai_messages(
        self, system_prompt: str, messages: list[LLMMessage]
    ) -> list[dict]:
        result = [{"role":"system", "content":system_prompt}]
        result+= [{"role": m.role, "content": m.content} for m in messages]
        return result

    def _to_openai_tools(
        self, tools: list[ToolSchema] | None
    ) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            }
            for t in tools
        ]    

    def complete(
        self,
        system_prompt: str,
        messages: list[LLMMessage],
        tools: list[ToolSchema] | None = None, 
    ) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "messages": self._to_openai_messages(system_prompt, messages),
            "max_completion_tokens": self._max_tokens,
        }
        openai_tools= self._to_openai_tools(tools)
        if openai_tools:
            kwargs["tools"] = openai_tools

        response = self._client.chat.completions.create(**kwargs)

        choice = response.choices[0]
        message = choice.message

        tool_call = None
        if message.tool_calls:
            raw = message.tool_calls[0]
            try:
                arguments = json.loads(raw.function.arguments)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "openai provider: tool %r returned invalid JSON arguments: %r",
                    raw.function.name,
                    raw.function.arguments
                )
                raise StructuredOutputError(
                    f"tool {raw.function.name!r} returned invalid JSON arguments"
                ) from exc
                
            tool_call = ToolCall(
                name=raw.function.name,
                arguments=arguments
            )
        return LLMResponse(
            text=message.content,
            tool_call=tool_call,
            stop_reason=choice.finish_reason
        )    