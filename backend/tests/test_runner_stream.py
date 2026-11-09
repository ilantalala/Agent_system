import env  # noqa: F401

import asyncio
from collections.abc import AsyncIterator
from typing import Any
import unittest
from unittest.mock import patch

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_core.tools import tool
from pydantic import Field

from app.runtime.events import DoneEvent, TokenEvent, ToolCallEvent, ToolResultEvent
from app.runtime.nodes import STEP_LIMIT_MESSAGE
from app.runtime.runner import AgentDefinition, AgentRunner


class Script:
    def __init__(self, rounds: list[list[AIMessageChunk] | Exception]) -> None:
        self.rounds = iter(rounds)
        self.history: list[list[BaseMessage]] = []


class ScriptedModel(BaseChatModel):
    script: Any = Field(exclude=True)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> 'ScriptedModel':
        return self

    def _generate(self, *args: Any, **kwargs: Any) -> ChatResult:
        raise AssertionError("Streaming expected")

    async def _astream(self, messages: list[BaseMessage], **kwargs: Any) -> AsyncIterator[ChatGenerationChunk]:
        self.script.history.append(messages)
        chunks = next(self.script.rounds)
        if isinstance(chunks, Exception):
            raise chunks
        for chunk in chunks:
            yield ChatGenerationChunk(message=chunk)


@tool
def echo(value: str) -> str:
    """Echo the supplied value."""
    return value


@tool
def fail(value: str) -> str:
    """Fail before producing a result."""
    raise RuntimeError("tool crashed")


def request(name: str = "echo", ident: str = "call-1") -> list[AIMessageChunk]:
    return [
        AIMessageChunk(content="Let me check..."),
        AIMessageChunk(content="", tool_call_chunks=[{"name": name, "id": ident, "args": '{"value":', "index": 0}]),
        AIMessageChunk(content="", tool_call_chunks=[{"name": None, "id": None, "args": '"hello"}', "index": 0}]),
    ]


def answer(text: str) -> list[AIMessageChunk]:
    return [AIMessageChunk(content=""), AIMessageChunk(content=text)]


class RunnerStreamTests(unittest.IsolatedAsyncioTestCase):
    def definition(self, rounds: list[list[AIMessageChunk] | Exception], tools: list[Any] | None = None) -> AgentDefinition:
        return AgentDefinition("system", ScriptedModel(script=Script(rounds)), tools or [])

    async def test_order_complete_arguments_and_final_reply(self) -> None:
        definition = self.definition([request(), answer("Final")], [echo])
        events = [event async for event in AgentRunner(max_tool_rounds=1).stream(definition, "thread", "question")]
        self.assertEqual([type(event) for event in events], [TokenEvent, ToolCallEvent, ToolResultEvent, TokenEvent, DoneEvent])
        self.assertEqual(events[1].args, {"value": "hello"})
        self.assertEqual(events[2], ToolResultEvent(id="call-1", name="echo", content="hello"))
        self.assertEqual(events[-1], DoneEvent(reply="Final"))
        self.assertEqual([event.text for event in events if isinstance(event, TokenEvent)], ["Let me check...", "Final"])
        for event in events:
            self.assertIsInstance(event.model_dump(), dict)
            event.model_dump_json()

    async def test_tool_error_result(self) -> None:
        definition = self.definition([request("unknown"), answer("handled")], [echo])
        events = [event async for event in AgentRunner(max_tool_rounds=1).stream(definition, "a", "hi")]
        result = next(event for event in events if isinstance(event, ToolResultEvent))
        self.assertTrue(result.is_error)
        self.assertEqual(result.id, "call-1")
        self.assertEqual(result.name, "unknown")
        self.assertEqual(events[-1], DoneEvent(reply="handled"))

    async def test_history_and_thread_isolation(self) -> None:
        runner = AgentRunner(max_tool_rounds=1)
        definition = self.definition([answer("first"), answer("second"), answer("other")])
        self.assertEqual(await runner.run(definition, "a", "one"), "first")
        self.assertEqual(await runner.run(definition, "a", "two"), "second")
        await runner.run(definition, "b", "three")
        histories = definition.model.script.history
        self.assertEqual([m.text for m in histories[1]], ["system", "one", "first", "two"])
        self.assertEqual([m.text for m in histories[2]], ["system", "three"])

    async def test_run_drains_stream(self) -> None:
        consumed: list[bool] = []

        async def stream(*args: Any) -> AsyncIterator[Any]:
            yield TokenEvent(text="earlier")
            yield DoneEvent(reply="final")
            consumed.append(True)

        runner = AgentRunner(max_tool_rounds=1)
        with patch.object(runner, "stream", stream):
            self.assertEqual(await runner.run(self.definition([]), "a", "hi"), "final")
        self.assertEqual(consumed, [True])

    async def test_step_limit(self) -> None:
        definition = self.definition([request()], [echo])
        events = [event async for event in AgentRunner(max_tool_rounds=0).stream(definition, "a", "hi")]
        self.assertFalse(any(isinstance(event, (ToolCallEvent, ToolResultEvent)) for event in events))
        self.assertEqual(events[-1], DoneEvent(reply=STEP_LIMIT_MESSAGE))
        tokens = "".join(event.text for event in events if isinstance(event, TokenEvent))
        self.assertEqual(tokens.count(STEP_LIMIT_MESSAGE), 1)

    async def test_exception_has_no_done(self) -> None:
        events: list[Any] = []
        with self.assertRaisesRegex(RuntimeError, "model crashed"):
            async for event in AgentRunner(max_tool_rounds=1).stream(self.definition([RuntimeError("model crashed")]), "a", "hi"):
                events.append(event)
        self.assertFalse(any(isinstance(event, DoneEvent) for event in events))

    async def test_interrupted_checkpoint_repair(self) -> None:
        runner = AgentRunner(max_tool_rounds=1)
        definition = self.definition([request("fail"), answer("recovered")], [fail])
        events: list[Any] = []
        with self.assertRaisesRegex(RuntimeError, "tool crashed"):
            async for event in runner.stream(definition, "a", "first"):
                events.append(event)
        self.assertTrue(any(isinstance(event, ToolCallEvent) for event in events))
        self.assertFalse(any(isinstance(event, DoneEvent) for event in events))
        recovered = [event async for event in runner.stream(definition, "a", "next")]
        self.assertEqual(recovered, [TokenEvent(text="recovered"), DoneEvent(reply="recovered")])
        history = definition.model.script.history[-1]
        self.assertIsInstance(history[-3], AIMessage)
        self.assertEqual(history[-2], ToolMessage(content="Interrupted before this tool ran.", tool_call_id="call-1", name="fail", status="error", id=history[-2].id))
        self.assertIsInstance(history[-1], HumanMessage)

    async def test_disconnect_before_commit_needs_no_repair(self) -> None:
        calls: list[str] = []

        @tool
        def tracked_echo(value: str) -> str:
            """Record the supplied value and echo it."""
            calls.append(value)
            return value

        runner = AgentRunner(max_tool_rounds=1)
        definition = self.definition([request("tracked_echo"), answer("recovered")], [tracked_echo])
        stream = runner.stream(definition, "a", "first")
        try:
            async for event in stream:
                if isinstance(event, ToolCallEvent):
                    self.assertEqual(event.id, "call-1")
                    break
            else:
                self.fail("Stream ended before a tool call")
        finally:
            await stream.aclose()
        self.assertEqual(calls, [])

        recovered = [event async for event in runner.stream(definition, "a", "next")]
        self.assertEqual(recovered, [TokenEvent(text="recovered"), DoneEvent(reply="recovered")])
        self.assertEqual(calls, [])
        history = definition.model.script.history[-1]
        self.assertEqual([type(message) for message in history], [SystemMessage, HumanMessage, HumanMessage])
        self.assertEqual([message.text for message in history], ["system", "first", "next"])

    async def test_disconnect_while_tool_runs_is_repaired(self) -> None:
        started = asyncio.Event()

        @tool
        async def slow_echo(value: str) -> str:
            """Echo the supplied value after a delay."""
            started.set()
            await asyncio.sleep(3600)
            return value

        runner = AgentRunner(max_tool_rounds=1)
        definition = self.definition([request("slow_echo"), answer("recovered")], [slow_echo])

        async def consume() -> None:
            async for event in runner.stream(definition, "a", "first"):
                pass

        task = asyncio.create_task(consume())
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
        finally:
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        recovered = [event async for event in runner.stream(definition, "a", "next")]
        self.assertEqual(recovered[-1], DoneEvent(reply="recovered"))
        history = definition.model.script.history[-1]
        self.assertIsInstance(history[-3], AIMessage)
        self.assertEqual(history[-3].tool_calls[0]["id"], "call-1")
        self.assertEqual(history[-2], ToolMessage(content="Interrupted before this tool ran.", tool_call_id=history[-3].tool_calls[0]["id"], name="slow_echo", status="error", id=history[-2].id))
        self.assertIsInstance(history[-1], HumanMessage)
        self.assertEqual(history[-1].content, "next")
