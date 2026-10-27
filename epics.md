# Epics & User Stories — Agent Builder Platform (LangGraph edition)

Ordered so each epic is buildable and testable on its own before moving to
the next. Each epic lists the concepts it's meant to teach — use this to
tell Claude Code "explain X as we build this" going in.

**Status:** Epics 1–3 are done. Epics 4–5 are **deferred** (not built yet —
skipped to get to the LangChain migration and WhatsApp sooner). Epics 6–7
are a **migration** of existing code (old Epics 4–6) onto
LangChain/LangGraph. Epics 8 onward are new work. Epic 12's infrastructure
(Redis, WAHA) is already started.

Epic branches merge into `dev`; dependencies are checked against `dev`.

Old → new numbering: old 1–3 → 1–3 · old 9 → 4 · old 10 → 5 ·
old 4 → 6 · old 5+6 → 7 · old 7 → 9 · old 8 → 10 · old 11 → 12.

---

## Migration rules (read before Epic 6)

- **Endpoints don't change.** Every existing route keeps its path and its
  request/response shape, so the frontend (Epic 5) keeps working. Only the
  code behind the route changes.
- **Old code is deleted last.** Build the LangGraph version next to the old
  one, verify it passes the same manual checks, switch the route over, then
  delete the old code path.
- **Two kinds of storage, on purpose:**
  - The LangGraph **checkpointer** (Postgres) is the graph's working memory:
    state between turns, keyed by `thread_id`.
  - Our own **conversations/messages tables** are the product record: what
    the UI, the admin screens and the audit log read.
- **One runtime for everything.** The test chat, WhatsApp and (later)
  automations all call the same runtime graph through one `AgentRunner`
  interface. No second code path for "real" traffic.

---

## Epic 1 — Project foundations ✅
*Concepts: FastAPI app structure, Pydantic settings, Alembic basics*

- Running FastAPI app with a health-check route.
- Environment config via Pydantic settings (`.env`).
- Postgres via SQLAlchemy, Alembic migrations set up.

## Epic 2 — Auth ✅
*Concepts: password hashing, JWT, FastAPI dependencies, OAuth2 password flow*

- Sign up, log in with JWT, `get_current_user`, `role` + `require_admin`.

## Epic 3 — Agents: data model & ownership ✅
*Concepts: SQLAlchemy relationships/FKs, dependency composition, authorization*

- Create, list, delete agents; `get_owned_agent(agent_id, user)` used by
  every agent route.

## Epic 4 — Admin dashboard & audit log ⏸ deferred
*Concepts: role-based views, reusing routes, audit logging*

- All agents across users; admin opens any agent through the owner's
  screens; "viewing as admin" banner; every admin action logged; filterable
  audit log.
- Note for later epics: every new agent route (test chat, approval,
  WhatsApp connect) must go through `get_owned_agent` so admin access and
  audit logging keep working without extra code.

## Epic 5 — Frontend integration ⏸ deferred
*Concepts: React + authenticated API, basic state management*

- Login/signup, agent dashboard, separate builder and test chat screens.

---

## Epic 6 — Model layer on LangChain (migration of old Epic 4)
*Concepts: LangChain chat models as the provider adapter, `init_chat_model`,
`bind_tools`, `with_structured_output`, BYOK*

- As a developer, I want a `get_chat_model(agent, user)` factory that
  returns a LangChain chat model, so LangChain's model interface replaces
  my custom provider adapter.
- As a developer, I want the factory to support OpenAI, Anthropic and a
  local Ollama `qwen3:32b`, selected by settings, so I can iterate for free
  and verify against the real models.
- As a developer, I want the API key passed per call from the user's stored
  key (BYOK), never from a global env var in production, so each client
  pays for their own usage.
- As a developer, I want structured output through `with_structured_output`
  with a JSON-parse fallback for the local model, so shaky local tool
  calling still doesn't break the flow.
- As a developer, I want the old `call_llm` callers switched to the factory
  and `call_llm` deleted, so there is one way to call a model.

## Epic 7 — Builder graph (migration of old Epics 5 + 6)
*Concepts: `StateGraph`, typed state with the `add_messages` reducer, nodes,
conditional edges, tool calls inside a node, Postgres checkpointer,
`thread_id`, the evaluator-optimizer loop as a graph*

- As a developer, I want a `BuilderState` (messages, draft, review result,
  status), so everything the builder knows lives in one typed object.
- As a developer, I want an `architect` node that runs my existing
  architect prompt and the `propose_draft` tool, so the interview logic is
  ported, not rewritten.
- As a developer, I want a `reviewer` node that scores the draft against
  the existing rubric with structured output, so review results are data,
  not prose.
- As a developer, I want a conditional edge after the reviewer:
  - gaps found → back to `architect`, with the gaps in state so its next
    question targets them;
  - draft passes → a `mark_ready` node, then END.

  So the loop is visible in the graph, not hidden in `if` statements.
- As a developer, I want one graph run per user message, with
  `thread_id = builder conversation id` and an `AsyncPostgresSaver`
  checkpointer, so the builder resumes correctly after a restart.
- As a developer, I want the builder chat endpoint to call the graph while
  keeping its request/response shape, and to keep writing to the messages
  table, so the frontend and admin screens don't notice the change.
- As a user, I want to be told when my draft is ready, so I know to move to
  testing.

## Epic 8 — Runtime graph and `AgentRunner`
*Concepts: the tool-calling loop as a graph (agent node + `ToolNode` +
`tools_condition`), `recursion_limit` as a safety cap, interfaces that hide
the framework*

- As a developer, I want a runtime graph that takes an agent definition
  (system prompt, enabled tools, model) and a conversation, and loops
  model → tools → model until it has an answer, so every channel shares one
  agent loop.
- As a developer, I want an `AgentRunner.run(definition, thread_id,
  message)` interface in front of the graph, so callers never import
  LangGraph directly and the framework can be swapped later.
- As a developer, I want a cap on tool calls per turn (`recursion_limit`)
  and a friendly fallback message when it's hit, so a looping agent can't
  burn the client's tokens.

## Epic 9 — Test chat (old Epic 7)
*Concepts: same code path for preview and production, streaming with
`astream(stream_mode="messages")`, SSE*

- As a user, I want to chat with my agent using the **draft** prompt, so I
  can see how it actually behaves.
- As a developer, I want the test chat to call `AgentRunner` with the draft
  definition, so test and production can never drift.
- As a user, I want the reply streamed token by token, so the test chat
  feels live.
- As a user, I want tool calls shown inline (collapsible), so I can see
  what my agent did.
- As a developer, I want test threads kept separate from future live
  threads (e.g. `thread_id = "test:{agent_id}:{conversation_id}"`), so test
  history never leaks into WhatsApp conversations.

## Epic 10 — Approval & finalize (old Epic 8)
*Concepts: state machines, explicit confirmation UX, versioning*

- As a user, I want an explicit "finalize this agent" confirmation, so an
  offhand "looks good" in chat doesn't lock in my prompt.
- As a developer, I want `finalize` to copy the draft definition to a new
  immutable **version**, mark it live and set `status = approved`, so
  there's a clear live/not-live boundary and rollback is possible.
- As a developer, I want finalize to be a plain API endpoint, not something
  the builder graph decides, so approval is always a human action.

## Epic 11 — Tool Registry and first integrations
*Concepts: tool schemas, read vs write tools, OAuth 2.0 per user,
`langchain-mcp-adapters`, encrypting secrets at rest*

- As a developer, I want a Tool Registry that returns the tools an agent
  may use from its definition, so the runtime graph never decides which
  tools exist.
- As a developer, I want every tool marked read or write, so write tools
  can require owner approval later.
- As a user, I want to connect Google Calendar (OAuth) and let my agent
  check availability and book meetings, so it can do real work.
- As a user, I want to connect a remote MCP server by URL and choose which
  of its tools my agent may use, so I can plug in any integration.
- As a developer, I want OAuth tokens and API keys encrypted at rest and
  never returned to the frontend, so a database leak doesn't leak clients'
  accounts.

## Epic 12 — WhatsApp via Redis + arq (rewrite of old Epic 11)
*Concepts: webhooks, adapter pattern for channels, Docker, background job
queues, idempotency, distributed locks, TTL keys, rate limiting*

Depends on Epic 10: only an agent with `status = approved` can connect.

Rule of thumb: Postgres holds anything that must survive (messages,
connection status, audit log). Redis holds only what is safe to lose (jobs
in flight, locks, counters, short-lived keys).

### Infrastructure

*Started early (on `epic-11-waha-redis`): Redis client, WAHA client and a
WhatsApp router exist as work in progress.*

- As a developer, I want Redis (and WAHA, for development only) running in
  docker-compose, so I have a queue and a test WhatsApp gateway locally.
- As a developer, I want one Redis connection (URL from settings, exposed
  as a FastAPI dependency), so Redis access isn't scattered through routes.
- As a developer, I want a `ChannelAdapter` interface (`parse_webhook`,
  `send_text`, `connection_status`) with a `WahaAdapter` first, so the
  official Cloud API adapter (Epic 13) drops in without touching the
  message flow.

### Connecting (development path, WAHA)

- As a user, I want a "connect WhatsApp" action on an approved agent that
  shows a QR code, so I can link a test number.
- As a developer, I want the QR code in Redis with a short TTL, so an
  expired code disappears on its own.
- As a user, I want to see the connection status (disconnected / pending
  scan / connected), so I know if it needs attention.

### Message flow

- As a developer, I want the webhook to verify the request, enqueue an
  `arq` job and return 200 immediately, so a slow LLM call never causes a
  timeout and redelivery.
- As a developer, I want a separate arq worker that consumes the queue,
  calls `AgentRunner` with the **live** version and sends the reply
  through the adapter, so message handling survives an API restart and
  scales on its own.
- As a developer, I want each incoming message ID recorded with
  `SET NX` + TTL before enqueueing, so a redelivered webhook never produces
  a duplicate reply.
- As a developer, I want `thread_id = "wa:{agent_id}:{contact}"`, so each
  customer has their own conversation memory in the checkpointer.
- As a developer, I want a per-contact lock while the runner works, so two
  messages from the same contact are never processed at once and replies
  stay in order.
- As a user, I want messages sent in quick succession buffered for a few
  seconds and answered once, so my agent doesn't reply three times to one
  thought.
- As a developer, I want every incoming and outgoing message saved to the
  messages table, so the conversation inbox and admin screens can show
  them.

### Protection

- As a developer, I want a per-contact and per-agent rate limit, so a
  spammy contact or a bot loop can't run up the client's LLM bill.
- As an admin, I want to force-disconnect any agent's WhatsApp, so I can
  stop a misbehaving agent immediately.
- As a developer, I want force-disconnect to drop that agent's queued jobs
  and buffered messages, so nothing is sent after it's stopped.

## Epic 13 — Official WhatsApp Cloud API (production path)
*Concepts: Meta webhooks and signature verification, Embedded Signup,
Coexistence, the 24-hour window, message templates*

Needs Meta Tech Provider approval — start that application early.

- As a developer, I want a `CloudApiAdapter` behind the same
  `ChannelAdapter` interface, verifying `X-Hub-Signature-256`, so
  production traffic uses the official API with no change to the message
  flow.
- As a user, I want to connect my WhatsApp Business app number through
  Embedded Signup and scan the QR from the Business app, so I keep using
  the app while my agent answers.
- As a developer, I want messages the owner sends from the Business app to
  pause the agent on that thread, so a human can take over.
- As a developer, I want replies outside the 24-hour window blocked unless
  they use an approved template, so we never violate Meta's rules.

## Epic 14 — Automations
*Concepts: cron expressions, polling with `FOR UPDATE SKIP LOCKED`, arq
cron jobs, event triggers*

- As a user, I want to ask the Architect for an automation ("every Sunday
  at 9, send me new leads"), so my agent can act on a schedule.
- As a developer, I want automations stored as rows (trigger, goal,
  allowed tools, output channel, `next_run_at`), so schedules are visible
  and editable.
- As a developer, I want an arq cron job every minute that picks due rows,
  enqueues `run_automation` and computes the next run with `croniter`, so
  schedules created at runtime just work.
- As a developer, I want event triggers (e.g. new CRM lead) to enqueue
  `run_automation` directly, so automations can react, not only wait.

---

## How to use this with Claude Code

Work through epics **in order** — each depends on the state left by the
one before it. Within an epic, before writing code:
1. Ask Claude Code to explain the concept the story is built around (see
   the concept line under each epic heading).
2. Plan the story together — what node/route/model/function, what it
   depends on — before implementation.
3. Implement it, then verify it manually (curl/Postman or a quick script)
   before moving to the next story.

For the migration epics (6 and 7), add one step before planning: ask Claude
Code to read the existing code for that feature and list what will be
ported, what will be replaced, and what will be deleted.

Don't let it jump ahead to a later epic's code while explaining an earlier
one — one epic at a time keeps the "why" attached to the "what."