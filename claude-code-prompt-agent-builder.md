# Build: AI Agent Builder Platform (Phase 1 — no WhatsApp integration)

## How to work with me on this

Read `CLAUDE.md` at the repo root first — it has the full working rules
(how we build each story together, who writes the code, session/branch
workflow). Everything there applies to this whole project, not just one
part of the stack.

Build a multi-user web application where users create custom LLM agents by
being interviewed by a "prompt architect" meta-agent, review the resulting
system prompt with a "reviewer" agent, test the agent live, and approve it.
Admins can see and fully access every user's agents, with every admin
action logged.

WhatsApp/WAHA integration is now in scope as Epic 11 of the accompanying
`epics-and-user-stories.md` — build it last, after approval (Epic 8) is
working, since connecting to WhatsApp should require an approved agent.

## Tech stack

- Backend: Python 3.11+, FastAPI, SQLAlchemy + Alembic for migrations
- Database: PostgreSQL
- LLM calls: via a provider abstraction (see below) — do not hard-code the
  Anthropic SDK into route/business logic
- Frontend: React + TypeScript, Tailwind for styling
- Auth: JWT-based session auth
- Package/dep management: your standard choice for each language (uv/pip
  for Python, npm/pnpm for the frontend) — pick one and be consistent

## LLM provider abstraction (for cost-free local testing)

A user has many agents (see data model below — this is the default shape,
not an add-on), and local development/testing will involve a lot of LLM
calls while iterating on the architect and reviewer prompts. To avoid
burning API budget on that, build one `call_llm(system_prompt, messages,
tools=None) -> LLMResponse` function behind a provider interface, selected
by an env var (`LLM_PROVIDER=anthropic` | `ollama`), not scattered
if/else calls through the codebase:

- **`anthropic`**: the real Claude API, for staging/production and for
  final verification that a prompt behaves correctly.
- **`ollama`**: points at a local Ollama instance (OpenAI-compatible
  endpoint) for free iteration during development. Default to `qwen3:32b`
  (strong tool-calling reliability, comfortably fits 64GB unified memory
  on Apple Silicon) — fall back to `qwen3:14b` if response latency during
  iteration is too slow in practice. Make the model name configurable via
  env var, not hard-coded, so it's easy to swap.

Important caveat to design around: local models are meaningfully weaker
at reliable structured/tool output than Claude. The `propose_draft` tool
call (architect) and the reviewer's structured `{ready, missing}` output
are the two places this bites hardest. Handle it like this:
- Define both as explicit JSON schemas in the provider-agnostic layer.
- For the `anthropic` provider, use native tool calling.
- For the `ollama` provider, use Ollama's tool-calling support where the
  chosen model has it, but add a fallback JSON-parse path (instruct the
  model to output only JSON, strip markdown fences, parse) since local
  tool-calling reliability varies by model/version.
- Log/flag when the local provider fails to produce valid structured
  output, rather than silently erroring, so it's obvious during dev
  whether a failure is a prompt problem or a local-model limitation.

Keep this env-var-switchable per environment, not per request — the goal
is "free iteration locally, verify against the real model before
shipping a prompt change," not runtime provider mixing.

## Data model

**users**
- id, email (unique), hashed_password, role (`user` | `admin`), created_at

**agents**
- id, owner_id (FK → users), name
- system_prompt (nullable — the live, approved prompt)
- draft_system_prompt (nullable — what the architect is iterating on)
- status: enum `drafting` | `in_review` | `ready_to_test` | `approved`
- whatsapp_session_name, whatsapp_status (nullable columns, unused this
  phase — placeholders for the future WAHA integration)
- created_at, updated_at

**conversations**
- id, agent_id (FK), kind: enum `builder` | `test`
  (`builder` = chat with the prompt architect; `test` = chat with the
  live/draft agent itself)
- created_at

**messages**
- id, conversation_id (FK), role (`user` | `assistant`), content, created_at

**audit_logs**
- id, admin_id (FK → users), agent_id (FK → agents), action (free text,
  e.g. `viewed_agent`, `edited_prompt`, `sent_test_message`,
  `disconnected_whatsapp`), metadata (JSON, nullable), created_at

## Core features, in build order

### 1. Auth
Signup, login, JWT issuance, `role` on the user. A `get_current_user`
FastAPI dependency, and a `require_admin` dependency for admin-only routes.

### 2. Agent ownership + access control
A single reusable dependency, `get_owned_agent(agent_id, user)`, used by
**every** agent-scoped route:
- Returns the agent if `agent.owner_id == user.id`
- Returns the agent if `user.role == 'admin'`
- Raises 404/403 otherwise

Every route below must go through this — never query an agent by ID
without it.

### 3. Prompt architect (builder chat)
A specialized, fixed system prompt (write this carefully — it's the most
important prompt in the app) that interviews the user conversationally,
one focused question at a time, to establish: the agent's role/persona,
core tasks, explicit non-goals, tone, output format, example interactions,
and edge-case/refusal handling.

It should have a `propose_draft` tool it calls once it has enough
information, with the draft system prompt as a structured argument
(don't parse this from free text). Calling this tool:
- Writes to `agent.draft_system_prompt`
- Sets `agent.status = 'in_review'`
- Triggers the reviewer (step 4)

### 4. Reviewer agent
Runs automatically whenever `draft_system_prompt` is updated. Its own
fixed system prompt evaluates the draft against a rubric: role clarity,
task coverage, tone specified, output format specified, edge cases /
refusals covered, examples present. Returns structured output:
`{ ready: bool, missing: string[] }`.

- If not ready: missing items get surfaced back into the builder chat as
  the architect's next question.
- If ready: `agent.status = 'ready_to_test'`, and the builder chat shows a
  message pointing the user to the test screen.

### 5. Test chat screen
A separate conversation (`kind = 'test'`) where the user talks directly
to their agent, using `draft_system_prompt` live — the exact same LLM-call
code path that will eventually run in production, no separate "preview"
logic.

### 6. Approval → finalize
Do not auto-finalize from message content alone. When the user's language
in the test chat sounds like approval, surface an explicit confirm action
in the UI ("Finalize this agent?"). On confirm:
- Copy `draft_system_prompt` → `system_prompt`
- `agent.status = 'approved'`

### 7. Admin dashboard
Admin-only frontend route + backend routes (gated by `require_admin`).
Must show:
- All agents across all users: owner email, name, status
- Message volume / last-active time per agent
- Full access into any agent — same builder chat, test chat, and prompt
  views a regular owner gets, via the same `get_owned_agent` bypass, not a
  separate parallel implementation
- A visible "viewing as admin — owner: {email}" banner whenever an admin
  is inside an agent they don't own

### 8. Audit log
Every admin action on an agent that isn't their own gets logged:
`admin_id, agent_id, action, metadata, created_at`. At minimum, log:
viewing an agent's prompt/conversations, editing a prompt, sending a test
message, and any status change. Surface this as a simple, filterable list
in the admin dashboard (filter by admin, by agent, by date range).

## API surface (suggested)

```
POST   /auth/signup
POST   /auth/login

GET    /agents                     # list — current user's agents (they may have several), or all if admin
POST   /agents                     # create new agent (drafting)
GET    /agents/{id}                # via get_owned_agent
DELETE /agents/{id}

POST   /agents/{id}/builder/messages   # chat with prompt architect
GET    /agents/{id}/builder/messages

POST   /agents/{id}/test/messages      # chat with the agent itself
GET    /agents/{id}/test/messages

POST   /agents/{id}/finalize           # promote draft -> live, requires confirm

GET    /admin/agents                   # all agents, admin only
GET    /admin/audit-logs               # filterable, admin only
```

## Notes for implementation

- Keep the architect's and reviewer's system prompts in their own files
  (not inlined in route handlers) so they're easy to iterate on.
- Write the `propose_draft` and any reviewer structured-output schemas as
  explicit Pydantic models / tool schemas — don't rely on regex-parsing
  model text.
- Seed one admin user via a migration or CLI command for initial setup.
- Include Alembic migrations for all tables above.
- A minimal test suite for the ownership-check dependency is worth having
  early, since every route depends on it being correct.