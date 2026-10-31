import json
import logging
from typing import TypeVar

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage
from langchain_core.messages.tool import ToolCall
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """The model was asked for structured data but returned something unusable."""


def _parse_json_text(text: str) -> dict | None:
    # Local models sometimes write the JSON as plain text (often fenced in
    # ```json ... ```) instead of using native structured output / tool calls.
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else ""
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    text = text.strip()

    if not (text.startswith("{") or text.startswith("[")):
        return None  # a normal prose reply, not botched JSON

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("reply looked like JSON but did not parse; content=%r", text)
        raise StructuredOutputError("model returned JSON-looking text that was invalid") from exc

    return parsed if isinstance(parsed, dict) else None


async def invoke_structured(
    model: BaseChatModel, schema: type[T], messages: LanguageModelInput
) -> T:
    result = await model.with_structured_output(schema, include_raw=True).ainvoke(messages)
    if result["parsed"] is not None:
        return result["parsed"]

    raw: AIMessage = result["raw"]
    data = _parse_json_text(raw.text)
    if data is None:
        raise StructuredOutputError(
            f"model returned no {schema.__name__}: {result['parsing_error']!r}"
        )
    try:
        parsed = schema.model_validate(data)
    except ValidationError as exc:
        raise StructuredOutputError(
            f"model's JSON did not match {schema.__name__}"
        ) from exc
    logger.warning("recovered %s via JSON-parse fallback", schema.__name__)
    return parsed


def get_tool_call(message: AIMessage, fallback_tool_name: str) -> ToolCall | None:
    # The model may answer in prose (no tool call) or call a tool.
    if message.tool_calls:
        return message.tool_calls[0]

    if message.invalid_tool_calls:
        bad = message.invalid_tool_calls[0]
        logger.warning(
            "tool %r returned invalid JSON arguments: %r", bad["name"], bad["args"]
        )
        raise StructuredOutputError(f"tool {bad['name']!r} returned invalid JSON arguments")

    data = _parse_json_text(message.text)
    if data is None:
        return None
    logger.warning(
        "recovered tool %r via JSON-parse fallback (model did not emit a native tool_call)",
        fallback_tool_name,
    )
    return ToolCall(name=fallback_tool_name, args=data, id=None)
