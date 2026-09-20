import json
import logging
import httpx
from app.config import settings
from app.llm.base import (
    LLMMessage,
    LLMProvider,
    LLMResponse,
    StructuredOutputError,
    ToolCall,
    ToolSchema,
)
logger = logging.getLogger(__name__)

class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model= settings.ollama_model
        self._timeout = settings.ollama_timeout_seconds

    def _to_ollama_messages(
        self, system_prompt: str, messages: list[LLMMessage]
    ) -> list[dict]:
        result = [{"role":"system", "content": system_prompt}]
        result+= [{"role": m.role, "content": m.content} for m in messages]
        return result
    def _to_ollama_tools(
        self, tools: list[ToolSchema] | None
    ) -> list[dict] | None:
        if not tools:
            return None
        return [
            {
                "type":"function",
                "function": {
                    "name":t.name,
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
        tools: list[ToolSchema] | None =None,
    ) -> LLMResponse:
        payload ={
            "model":self._model,
            "messages":self._to_ollama_messages(system_prompt,messages),
            "stream":False
        }
        ollama_tools = self._to_ollama_tools(tools)
        if ollama_tools:
            payload["tools"] = ollama_tools
        response = httpx.post(
            f"{self._base_url}/api/chat",
            json=payload,
            timeout=self._timeout,
        )    
        response.raise_for_status()
        body=response.json()

        message = body.get("message", {})
        content = message.get("content") or None
        stop_reason=body.get("done_reason", "stop")

        tool_call = None
        if message.get("tool_calls"):
            fn = message["tool_calls"][0]["function"]
            tool_call = ToolCall(name=fn["name"], arguments=fn["arguments"])
        elif tools:
            tool_call = self._recover_tool_call(message.get("content", ""), tools)    
            if tool_call is not None:
                content = None
        return LLMResponse(text=content, tool_call=tool_call, stop_reason=stop_reason)        
    
    def _recover_tool_call(
        self, content: str, tools: list[ToolSchema]
    ) -> ToolCall | None:
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1] if "\n" in text else ""
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]
        text = text.strip()

        if not (text.startswith("{") or text.startswith("[")):
            return None  # a normal prose reply — not a botched tool call

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            logger.warning(
                "ollama provider: reply looked like JSON but did not parse; "
                "content=%r",
                content,
            )
            raise StructuredOutputError(
                "ollama returned no tool call and its JSON-looking text was invalid"
            ) from exc

        if not isinstance(parsed, dict):
            return None

        tool_name = tools[0].name
        logger.warning(
            "ollama provider: recovered tool %r via JSON-parse fallback "
            "(model did not emit a native tool_call)",
            tool_name,
        )
        return ToolCall(name=tool_name, arguments=parsed)