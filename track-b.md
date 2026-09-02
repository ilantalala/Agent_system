# Track B — Agent Intelligence

Owns: the LLM provider abstraction, the prompt architect, the reviewer
agent, test chat, and the approval state machine. Read `epics-00-
foundations-and-contract.md` first — Epic 1 there is a prerequisite, and
the contract section defines what you own vs. what Track A owns.

Branch naming: `track-b/epic-4-llm-provider`, `track-b/epic-5-architect`,
etc.

You depend on Track A's `agents` table and `get_owned_agent` existing
(Epic 3) before Epic 5 can really start — check in with them if you reach
that epic first.

---

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
  agent, so builder chat history persists. (Track A's admin dashboard
  reads these — keep the schema reasonably stable once it's in use.)
- As a developer, I want the architect's system prompt to ask one focused
  question at a time, so the interview feels conversational.
- As a developer, I want a `propose_draft` tool the architect calls when
  ready, so the draft is captured as structured data, not parsed from
  prose. Writes to `agent_prompt_state.draft_system_prompt`.

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
  to testing. Sets `agent_prompt_state.status = 'ready_to_test'`.

## Epic 7 — Test chat
*Concepts: reusing the same code path for "preview" vs "prod", conversation kinds*

- As a user, I want to chat directly with my agent using the draft
  prompt, so I can see how it actually behaves.
- As a developer, I want this to hit the exact same orchestration code as
  the (future) production agent, so there's no drift between test and
  real behavior. (This is the same function Track A's WAHA epic will
  call later — keep its signature something a transport layer can call
  without knowing it's WhatsApp.)

## Epic 8 — Approval & finalize
*Concepts: state machines, explicit confirmation UX, avoiding false-positive automation*

- As a user, I want an explicit "finalize this agent" confirmation, so an
  offhand "looks good" in chat doesn't accidentally lock in my prompt.
- As a developer, I want `finalize` to copy `draft_system_prompt` →
  `system_prompt` and set `status = approved`, so there's a clear
  live/not-live boundary. **This status flip is what Track A's WAHA epic
  gates on — let them know when this lands.**