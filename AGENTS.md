# AGENTS.md — Rules for coding agents (Codex, Cursor)

You are a worker agent. An orchestrator gives you one task with an explicit
list of files you may edit. Stay inside that list.

## Project
Agent Builder Platform: FastAPI backend, PostgreSQL (SQLAlchemy + Alembic),
LangChain/LangGraph, Redis + arq for background jobs. Code lives in `backend/`.
Roadmap: `EPICS.md`.

## Hard rules
- Never import LangGraph outside the runtime/builder graph modules.
  Callers use `AgentRunner` only.
- Every route that takes an agent id goes through `get_owned_agent`.
- Don't change existing endpoint paths or request/response shapes unless the
  task says so.
- Don't modify contract files named in your task.
- Don't add dependencies. If you need one, stop and say so in your summary.
- No network access: don't run pip/uv/npm installs.
- API keys come from the user's stored key (BYOK), never from global env
  vars in production code paths.

## Style
- Type hints everywhere; Pydantic models for request/response bodies.
- Async SQLAlchemy and async LangGraph APIs.
- Small functions, no dead code, no commented-out code.

## Tests
- Add tests in `backend/tests/`. Mock LLM calls; tests must run offline.
- Run: `cd backend && uv run python -m unittest discover -s tests -v`

## When done
Run tests, commit with `git add -A && git commit -m "epic-<N>: <summary>"`,
then print a short summary and any open questions.
