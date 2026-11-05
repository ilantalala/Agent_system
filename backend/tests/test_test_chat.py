import env  # noqa: F401

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies import get_current_user
from app.main import app
from app.models import Agent, Conversation, Message, User
from app.runtime.events import (
    DoneEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from app.runtime.tools import get_current_time


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    frames: list[tuple[str, dict]] = []
    for block in body.strip().split("\n\n"):
        if not block.strip():
            continue
        event_name = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_name = line.removeprefix("event: ")
            elif line.startswith("data: "):
                data = json.loads(line.removeprefix("data: "))
        frames.append((event_name, data))
    return frames


class FakeRunner:
    """Scripted stand-in; records args and never touches LangGraph."""

    def __init__(self, reply: str = "hello", stream_events=None, raise_after: int | None = None):
        self.reply = reply
        self.stream_events = stream_events or []
        self.raise_after = raise_after
        self.calls: list[tuple] = []

    async def run(self, definition, thread_id: str, message: str) -> str:
        self.calls.append(("run", definition, thread_id, message))
        return self.reply

    async def stream(self, definition, thread_id: str, message: str):
        self.calls.append(("stream", definition, thread_id, message))
        for i, event in enumerate(self.stream_events):
            if self.raise_after is not None and i == self.raise_after:
                raise RuntimeError("secret boom detail must never leak")
            yield event
        if self.raise_after is not None and self.raise_after >= len(self.stream_events):
            raise RuntimeError("secret boom detail must never leak")


class TestChatRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.Session()

        self.owner = User(
            email="owner@example.com",
            hashed_password="x",
            role="user",
        )
        self.other = User(
            email="other@example.com",
            hashed_password="x",
            role="user",
        )
        self.db.add_all([self.owner, self.other])
        self.db.flush()
        self.agent = Agent(
            name="Demo",
            owner_id=self.owner.id,
            draft_system_prompt="You are a helpful test agent.",
        )
        self.db.add(self.agent)
        self.db.commit()
        self.db.refresh(self.agent)
        self.db.refresh(self.owner)

        self.current_user = self.owner

        def override_get_db():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        def override_get_current_user():
            # Re-load so get_owned_agent's session can compare owner_id cleanly.
            return self.db.merge(self.current_user)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = override_get_current_user

        self.fake_model = MagicMock(name="fake-chat-model")
        self.get_chat_model_patcher = patch(
            "app.routers.test_chat.get_chat_model", return_value=self.fake_model
        )
        self.get_chat_model_patcher.start()

        self.runner = FakeRunner(
            reply="assistant reply",
            stream_events=[
                TokenEvent(text="Hi"),
                ToolCallEvent(id="c1", name="get_current_time", args={}),
                ToolResultEvent(id="c1", name="get_current_time", content="now"),
                DoneEvent(reply="streamed reply"),
            ],
        )
        app.state.agent_runner = self.runner
        # No `with` — lifespan must not run (no Postgres).
        self.client = TestClient(app)

    def tearDown(self):
        self.get_chat_model_patcher.stop()
        app.dependency_overrides.clear()
        self.db.close()
        self.engine.dispose()

    def _chat_url(self, agent_id: int | None = None) -> str:
        return f"/agents/{agent_id or self.agent.id}/test-chat/chat"

    def _stream_url(self, agent_id: int | None = None) -> str:
        return f"/agents/{agent_id or self.agent.id}/test-chat/stream"

    def test_chat_uses_runner_and_saves_turn(self):
        response = self.client.post(self._chat_url(), json={"content": "hello"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"message": {"role": "assistant", "content": "assistant reply"}},
        )

        self.assertEqual(len(self.runner.calls), 1)
        kind, definition, thread_id, message = self.runner.calls[0]
        self.assertEqual(kind, "run")
        self.assertEqual(message, "hello")
        self.assertEqual(definition.system_prompt, "You are a helpful test agent.")
        self.assertIs(definition.model, self.fake_model)
        self.assertIn(get_current_time, definition.tools)

        conversation = self.db.scalar(
            select(Conversation).where(
                Conversation.agent_id == self.agent.id, Conversation.kind == "test"
            )
        )
        self.assertIsNotNone(conversation)
        self.assertEqual(thread_id, f"test:{self.agent.id}:{conversation.id}")

        messages = self.db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.id)
        ).all()
        self.assertEqual(
            [(m.role, m.content) for m in messages],
            [("user", "hello"), ("assistant", "assistant reply")],
        )

    def test_chat_second_turn_reuses_conversation_and_thread_id(self):
        first = self.client.post(self._chat_url(), json={"content": "one"})
        self.assertEqual(first.status_code, 200)
        conversation = self.db.scalar(
            select(Conversation).where(
                Conversation.agent_id == self.agent.id, Conversation.kind == "test"
            )
        )
        expected_thread = f"test:{self.agent.id}:{conversation.id}"

        second = self.client.post(self._chat_url(), json={"content": "two"})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(self.runner.calls), 2)
        self.assertEqual(self.runner.calls[0][2], expected_thread)
        self.assertEqual(self.runner.calls[1][2], expected_thread)

        conversations = self.db.scalars(
            select(Conversation).where(
                Conversation.agent_id == self.agent.id, Conversation.kind == "test"
            )
        ).all()
        self.assertEqual(len(conversations), 1)

        messages = self.db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.id)
        ).all()
        self.assertEqual(len(messages), 4)

    def test_stream_forwards_events_saves_before_done_and_sets_headers(self):
        response = self.client.post(self._stream_url(), json={"content": "stream me"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/event-stream; charset=utf-8")
        self.assertEqual(response.headers["cache-control"], "no-cache")
        self.assertEqual(response.headers["x-accel-buffering"], "no")

        frames = _parse_sse(response.text)
        self.assertEqual(
            [name for name, _ in frames],
            ["token", "tool_call", "tool_result", "done"],
        )
        self.assertEqual(frames[0][1]["text"], "Hi")
        self.assertEqual(frames[-1][1]["reply"], "streamed reply")

        kind, definition, thread_id, message = self.runner.calls[0]
        self.assertEqual(kind, "stream")
        self.assertEqual(message, "stream me")
        self.assertIn(get_current_time, definition.tools)

        conversation = self.db.scalar(
            select(Conversation).where(
                Conversation.agent_id == self.agent.id, Conversation.kind == "test"
            )
        )
        self.assertEqual(thread_id, f"test:{self.agent.id}:{conversation.id}")
        messages = self.db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.id)
        ).all()
        self.assertEqual(
            [(m.role, m.content) for m in messages],
            [("user", "stream me"), ("assistant", "streamed reply")],
        )

    def test_stream_runner_raises_sends_error_no_done_no_save(self):
        self.runner.stream_events = [
            TokenEvent(text="partial"),
            DoneEvent(reply="should not save"),
        ]
        self.runner.raise_after = 1  # raise before yielding DoneEvent

        response = self.client.post(self._stream_url(), json={"content": "explode"})
        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertNotIn("secret boom", body)
        self.assertNotIn("must never leak", body)

        frames = _parse_sse(body)
        self.assertEqual([name for name, _ in frames], ["token", "error"])
        self.assertNotIn("done", [name for name, _ in frames])
        self.assertEqual(
            frames[-1][1]["message"],
            "Something went wrong while generating a reply.",
        )

        conversation = self.db.scalar(
            select(Conversation).where(
                Conversation.agent_id == self.agent.id, Conversation.kind == "test"
            )
        )
        self.assertIsNotNone(conversation)
        messages = self.db.scalars(
            select(Message).where(Message.conversation_id == conversation.id)
        ).all()
        self.assertEqual(messages, [])

    def test_chat_400_without_draft(self):
        self.agent.draft_system_prompt = None
        self.db.commit()
        response = self.client.post(self._chat_url(), json={"content": "hi"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Agent has no draft system prompt to test yet",
        )
        self.assertEqual(self.runner.calls, [])

    def test_stream_400_without_draft(self):
        self.agent.draft_system_prompt = None
        self.db.commit()
        response = self.client.post(self._stream_url(), json={"content": "hi"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["detail"],
            "Agent has no draft system prompt to test yet",
        )
        self.assertEqual(self.runner.calls, [])

    def test_chat_404_for_other_users_agent(self):
        self.current_user = self.other
        response = self.client.post(self._chat_url(), json={"content": "hi"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.runner.calls, [])

    def test_stream_404_for_other_users_agent(self):
        self.current_user = self.other
        response = self.client.post(self._stream_url(), json={"content": "hi"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.runner.calls, [])


if __name__ == "__main__":
    unittest.main()
