from typing import Any, Literal

from pydantic import BaseModel

# What a run looks like from outside the runtime. Callers read these events and
# never see LangGraph's own stream format, so the framework stays swappable.


class TokenEvent(BaseModel):
    type: Literal["token"] = "token"
    text: str


class ToolCallEvent(BaseModel):
    # Sent once the call is complete: args are the full parsed arguments.
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    args: dict[str, Any]


class ToolResultEvent(BaseModel):
    # id matches the ToolCallEvent it answers, so a UI can pair them.
    type: Literal["tool_result"] = "tool_result"
    id: str
    name: str
    content: str
    is_error: bool = False


class DoneEvent(BaseModel):
    # Always the last event of a run. reply is the final answer, the same text
    # AgentRunner.run returns; tokens from earlier model rounds aren't part of it.
    type: Literal["done"] = "done"
    reply: str


class ErrorEvent(BaseModel):
    # Sent by the route, not the runner: the runner raises, and by then the HTTP
    # status has already gone out. message is safe to show to the user.
    type: Literal["error"] = "error"
    message: str


RunEvent = TokenEvent | ToolCallEvent | ToolResultEvent | DoneEvent
StreamEvent = RunEvent | ErrorEvent


def to_sse(event: StreamEvent) -> str:
    return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"
