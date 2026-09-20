from app.llm.base import LLMMessage, LLMProvider, LLMResponse, ToolSchema

class FakeProvider(LLMProvider):
    def complete(
        self,
        system_prompt: str,
        messages: list[LLMMessage],
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        last_user= next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        return LLMResponse(
            text=f"[fake] system={system_prompt!r} last_user={last_user!r}",
            stop_reason="end_turn",
        )
        