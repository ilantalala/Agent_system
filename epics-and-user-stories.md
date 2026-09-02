# Epics & User Stories — Agent Builder Platform

Ordered so each epic is buildable and testable on its own before moving to
the next. Each story lists the concept it's meant to teach — use this to
tell Claude Code "explain X as we build this" going in.

---

## Epic 1 — Project foundations
*Concepts: FastAPI app structure, Pydantic settings, Alembic basics*

- As a developer, I want a running FastAPI app with a health-check route,
  so I have a working skeleton before adding real features.
- As a developer, I want environment config loaded via Pydantic settings
  (`.env` file), so secrets and config aren't hard-coded.
- As a developer, I want Postgres connected via SQLAlchemy with Alembic
  migrations set up and running an empty first migration, so the DB
  workflow is proven before real tables exist.

## Epic 2 — Auth
*Concepts: password hashing, JWT, FastAPI dependencies, OAuth2 password flow*

- As a new user, I want to sign up with email + password, so I have an
  account.
- As a returning user, I want to log in and receive a JWT, so I can make
  authenticated requests.
- As a developer, I want a `get_current_user` dependency, so any route
  can require a logged-in user with one line.
- As a developer, I want a `role` field on users and a `require_admin`
  dependency, so admin-only routes are enforceable later.

## Epic 3 — Agents: data model & ownership
*Concepts: SQLAlchemy relationships/FKs, FastAPI dependency composition, authorization patterns*

- As a user, I want to create an agent (just a name at first), so I have
  something to build on.
- As a user, I want to list *my* agents, so I can have several without
  seeing anyone else's.
- As a developer, I want a single `get_owned_agent(agent_id, user)`
  dependency used by every agent route, so ownership is enforced in one
  place, not repeated per-route.
- As a user, I want to delete an agent I own, so I can clean up
  experiments.

## Epic 4 — LLM provider abstraction
*Concepts: adapter pattern, structured output / tool calling, env-based config*

- As a developer, I want one `call_llm(...)` function behind a provider
  interface, so business logic never talks to a specific SDK directly.
- As a developer, I want an `anthropic` provider implementation, so I can
  verify behavior against the real model.
- As a developer, I want an `ollama` provider implementation pointed at a
  local `qwen3:32b`, so I can iterate for free.
- As a developer, I want a JSON-parse fallback for structured output on
  the local provider, so a local model's shakier tool-calling doesn't
  silently break the flow.

## Epic 5 — Prompt architect (builder chat)
*Concepts: conversation/message modeling, prompt design, tool-call handling*

- As a user, I want to describe my agent in a chat, so I don't have to
  write a system prompt myself.
- As a developer, I want conversations/messages tables scoped to an
  agent, so builder chat history persists.
- As a developer, I want the architect's system prompt to ask one focused
  question at a time, so the interview feels conversational.
- As a developer, I want a `propose_draft` tool the architect calls when
  ready, so the draft is captured as structured data, not parsed from
  prose.

## Epic 6 — Reviewer agent
*Concepts: structured output validation, evaluator-optimizer pattern, feedback loops*

- As a developer, I want a reviewer prompt with a fixed rubric (role
  clarity, tasks, tone, edge cases, examples), so draft quality is
  checked consistently.
- As a developer, I want the reviewer to run automatically after each
  draft update, so the user doesn't trigger it manually.
- As a user, I want missing items fed back into the architect chat as its
  next question, so the loop feels like one conversation, not two tools.
- As a user, I want to be told when my draft is ready, so I know to move
  to testing.

## Epic 7 — Test chat
*Concepts: reusing the same code path for "preview" vs "prod", conversation kinds*

- As a user, I want to chat directly with my agent using the draft
  prompt, so I can see how it actually behaves.
- As a developer, I want this to hit the exact same orchestration code as
  the (future) production agent, so there's no drift between test and
  real behavior.

## Epic 8 — Approval & finalize
*Concepts: state machines, explicit confirmation UX, avoiding false-positive automation*

- As a user, I want an explicit "finalize this agent" confirmation, so an
  offhand "looks good" in chat doesn't accidentally lock in my prompt.
- As a developer, I want `finalize` to copy `draft_system_prompt` →
  `system_prompt` and set `status = approved`, so there's a clear
  live/not-live boundary.

## Epic 9 — Admin dashboard & audit log
*Concepts: role-based views, reusing routes vs. duplicating them, audit logging*

- As an admin, I want to see all agents across all users with owner and
  status, so I have full visibility.
- As an admin, I want to open any user's agent through the same
  builder/test screens an owner uses, so there's one implementation, not
  two.
- As a user (or admin), I want a visible "viewing as admin" banner when
  an admin is inside someone else's agent, so it's never ambiguous whose
  agent is being touched.
- As an admin, I want every admin action on a non-owned agent logged
  (who, what, when), so there's accountability.
- As an admin, I want a filterable audit log view, so I can find a
  specific past action.

## Epic 10 — Frontend integration
*Concepts: tying a React app to a real auth'd API, basic state management*

- As a user, I want a login/signup screen, so I can access the app.
- As a user, I want a dashboard listing my agents with status, so I can
  jump into any of them.
- As a user, I want the builder chat and test chat as separate screens,
  so the two modes don't get confused.

## Epic 11 — WhatsApp integration via WAHA
*Concepts: webhooks, external REST API clients, Docker, event-driven message flow*

Depends on Epic 8 (approval) — connecting to WhatsApp should only be
possible for an agent with `status = approved`.

- As a developer, I want a self-hosted WAHA container running via
  docker-compose, so I have a local WhatsApp gateway to develop against.
- As a developer, I want a thin WAHA client (start session, get QR, send
  text) in the backend, so gateway calls aren't scattered through route
  code.
- As a user, I want a "connect WhatsApp" action on an approved agent that
  shows me a QR code, so I can link my WhatsApp number to it.
- As a developer, I want a `/webhooks/waha` endpoint that receives WAHA's
  session-status and incoming-message events, so connection state and
  messages reach the backend.
- As a user, I want my agent to reply on WhatsApp using the exact same
  orchestrator as the test chat, so its behavior matches what I already
  approved.
- As an admin, I want to force-disconnect any user's WhatsApp session, so
  I can shut down a misbehaving agent immediately.
- As a user, I want to see my agent's WhatsApp connection status
  (disconnected / pending scan / connected), so I know if it needs
  rescanning.

---

## How to use this with Claude Code

Work through epics **in order** — each depends on the state left by the
one before it. Within an epic, before writing code:
1. Ask Claude Code to explain the FastAPI/SQLAlchemy concept the story is
   built around (see the concept line under each epic heading).
2. Plan the story together — what route/model/function, what it depends
   on — before implementation.
3. Implement it, then verify it manually (curl/Postman or a quick script)
   before moving to the next story.

Don't let it jump ahead to a later epic's code while explaining an
earlier one — one epic at a time keeps the "why" attached to the "what."
