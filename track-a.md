# Track A — Platform & Access

Owns: user accounts, agent identity/ownership, admin visibility, the
frontend shell, and WhatsApp connectivity. Read `epics-00-foundations-and-
contract.md` first — Epic 1 there is a prerequisite, and the contract
section defines what you own vs. what Track B owns.

Branch naming: `track-a/epic-2-auth`, `track-a/epic-3-agents`, etc.

---

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
  place, not repeated per-route. **This is the function Track B imports —
  build it as a clean, standalone piece.**
- As a user, I want to delete an agent I own, so I can clean up
  experiments.

## Epic 9 — Admin dashboard & audit log
*Concepts: role-based views, reusing routes vs. duplicating them, audit logging*

- As an admin, I want to see all agents across all users with owner and
  status, so I have full visibility. (Status comes from Track B's
  `agent_prompt_state` — read it, don't own it.)
- As an admin, I want to open any user's agent through the same
  builder/test screens an owner uses, so there's one implementation, not
  two. (Those screens are Track B's — this story is about the access
  path into them, not rebuilding them.)
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
  so the two modes don't get confused. (The chat UIs themselves need
  Track B's endpoints to be live to fully wire up — you can build the
  shell and stub the API calls before that lands.)

## Epic 11 — WhatsApp integration via WAHA
*Concepts: webhooks, external REST API clients, Docker, event-driven message flow*

Everything except the final gate can be built independently of Track B.
The gate (only `approved` agents can connect) needs Epic 8 merged first —
see the contract doc.

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
  approved. (The orchestrator call itself is Track B's — you're wiring
  the transport around it.)
- As an admin, I want to force-disconnect any user's WhatsApp session, so
  I can shut down a misbehaving agent immediately.
- As a user, I want to see my agent's WhatsApp connection status
  (disconnected / pending scan / connected), so I know if it needs
  rescanning.