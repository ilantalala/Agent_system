import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_owned_agent
from app.llm.chat_model import get_chat_model
from app.models import Agent, Conversation
from app.orchestrator import save_turn
from app.runtime.events import DoneEvent, ErrorEvent, to_sse
from app.runtime.runner import AgentDefinition
from app.runtime.tools import DEV_TOOLS
from app.schemas import ChatMessage, TestChatRequest, TestChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents/{agent_id}/test-chat", tags=["test-chat"])

# Shown to the client on stream failure; never include exception text.
_STREAM_ERROR_MESSAGE = "Something went wrong while generating a reply."


# Test threads get their own prefix so test history can never mix with the
# builder's threads or live channels.
def test_thread_id(agent_id: int, conversation_id: int) -> str:
    return f"test:{agent_id}:{conversation_id}"


# The DB layer is still synchronous, so DB work runs in a worker thread and
# only the slow part — the runner's model calls — runs on the event loop.
def _start_turn(db: Session, agent: Agent) -> tuple[int, str, AgentDefinition]:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.agent_id == agent.id, Conversation.kind == "test"
        )
    )
    if conversation is None:
        conversation = Conversation(agent_id=agent.id, kind="test")
        db.add(conversation)
        db.flush()  # send the INSERT so the new row gets its id
    conversation_id = conversation.id
    thread_id = test_thread_id(agent.id, conversation_id)
    definition = AgentDefinition(
        system_prompt=agent.draft_system_prompt,
        # BYOK: the agent's owner pays, even when an admin is the one chatting.
        model=get_chat_model(agent, agent.owner),
        # Temporary stand-in until the Tool Registry (Epic 11) picks tools.
        tools=DEV_TOOLS,
    )
    # End the transaction last, so no connection is held across the model calls.
    db.commit()
    return conversation_id, thread_id, definition


def _finish_turn(
    db: Session, conversation_id: int, user_content: str, reply_text: str
) -> TestChatResponse:
    conversation = db.get(Conversation, conversation_id)
    save_turn(db, conversation, user_content, reply_text)
    db.commit()
    return TestChatResponse(message=ChatMessage(role="assistant", content=reply_text))


def _require_draft(agent: Agent) -> None:
    if agent.draft_system_prompt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Agent has no draft system prompt to test yet",
        )


@router.post("/chat", response_model=TestChatResponse)
async def test_chat(
    payload: TestChatRequest,
    request: Request,
    agent: Agent = Depends(get_owned_agent),
    db: Session = Depends(get_db),
):
    _require_draft(agent)
    conversation_id, thread_id, definition = await run_in_threadpool(_start_turn, db, agent)
    reply_text = await request.app.state.agent_runner.run(
        definition, thread_id, payload.content
    )
    return await run_in_threadpool(
        _finish_turn, db, conversation_id, payload.content, reply_text
    )


@router.post("/stream")
async def test_chat_stream(
    payload: TestChatRequest,
    request: Request,
    agent: Agent = Depends(get_owned_agent),
    db: Session = Depends(get_db),
):
    # Validate and open the turn before StreamingResponse so 400/404 stay real
    # HTTP errors, not frames stuck inside an already-started 200 stream.
    _require_draft(agent)
    conversation_id, thread_id, definition = await run_in_threadpool(_start_turn, db, agent)

    async def event_gen() -> AsyncIterator[str]:
        try:
            async for event in request.app.state.agent_runner.stream(
                definition, thread_id, payload.content
            ):
                # Persist before the client sees `done`, so `done` means saved.
                if isinstance(event, DoneEvent):
                    await run_in_threadpool(
                        _finish_turn,
                        db,
                        conversation_id,
                        payload.content,
                        event.reply,
                    )
                yield to_sse(event)
        except Exception:
            # Catch Exception only: CancelledError / GeneratorExit must propagate
            # so a client disconnect never saves a half-finished turn.
            logger.exception("test chat stream failed")
            yield to_sse(ErrorEvent(message=_STREAM_ERROR_MESSAGE))

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
