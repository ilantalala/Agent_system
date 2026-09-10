from abc import ABC, abstractmethod
from typing import Literal

from pydantic import BaseModel


class StructuredOutputError(Exception):
    """The model returned a tool call whose arguments weren't valid JSON."""
    

class LLMMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str

class ToolSchema(BaseModel):
    name: str
    description: str
    input_schema: dict

class ToolCall(BaseModel):
    name: str
    arguments: dict

class LLMResponse(BaseModel):
    text: str | None = None
    tool_call: ToolCall | None = None
    stop_reason: str

class LLMProvider(ABC):
    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        messages: list[LLMMessage],
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        ...
