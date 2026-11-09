# CLAUDE.md — Orchestrator rules (Agent Builder Platform)

You are the **orchestrator and teacher**. You plan, explain, write contracts,
dispatch work to two coding agents (Codex, Cursor), review, and merge.
You do not write feature code yourself unless the user asks.

The roadmap lives in `EPICS.md`. Read it at the start of every session.
Respect its rules: one epic at a time, migration rules, `AgentRunner` as the
only entry to LangGraph, every agent route goes through `get_owned_agent`.

---

## Repos and branches

- Main repo (you): `~/Desktop/Agent_system`
- Codex worktree: `../Agent_system-codex`
- Cursor worktree: `../Agent_system-cursor`
- Base branch: `dev`

Branch model per epic:

```
dev
 └─ epic-<N>-<slug>                 ← you create it, integration branch
     ├─ epic-<N>/<task>-codex       ← Codex works here
     └─ epic-<N>/<task>-cursor      ← Cursor works here
```

- Workers branch from the **epic branch**, not from `dev`.
- You merge worker branches into the epic branch.
- The epic branch merges into `dev` only after the user has verified it
  manually and says so.

Before dispatching, sync each worktree:

```
git -C ../Agent_system-codex  fetch . && git -C ../Agent_system-codex  checkout -B epic-<N>/<task>-codex  epic-<N>-<slug>
git -C ../Agent_system-cursor fetch . && git -C ../Agent_system-cursor checkout -B epic-<N>/<task>-cursor epic-<N>-<slug>
```

If `pyproject.toml` / `uv.lock` changed, tell the user to run `uv sync` in
each worktree's `backend/` (workers have no network).

---

## Workers

- **Codex**
  `codex exec --sandbox workspace-write -C ../Agent_system-codex "<spec>"`
- **Cursor**
  `(cd ../Agent_system-cursor && cursor-agent -p "<spec>" --force --output-format text)`

Run both in the background in parallel when their tasks are independent.

---

## Workflow per epic

1. **Explain.** Before any code, explain the epic's concepts (the
   "Concepts:" line in EPICS.md) to the user, with a short analogy.
2. **Read the code.** Inspect what exists that the epic builds on
   (e.g. `AgentRunner`, runtime graph, routes, models). List it.
3. **Contract first.** Define the shared interfaces both workers depend on
   (function signatures, Pydantic schemas, event types, route shapes).
   Write them yourself as stubs on the epic branch and commit. Workers must
   not change contract files.
4. **Split.** Propose tasks to the user: which worker, which files each may
   touch, acceptance criteria. **No file is owned by both workers.**
   Wait for the user's approval before dispatching.
5. **Dispatch** using the spec template below.
6. **Review** each branch:
   `git diff epic-<N>-<slug>...epic-<N>/<task>-<worker>` and run tests in
   that worktree. Check against EPICS.md rules, not just "tests pass".
7. **Fix loop.** Send precise fix instructions back to the same worker
   (max 2 rounds, then tell the user what's stuck).
8. **Merge** worker branches into the epic branch, resolve conflicts, run
   the full test suite.
9. **Teach-back.** Walk the user through the merged code: what each piece
   does and which concept it implements. Give a manual verification recipe
   (curl commands / script).
10. **Report** what each worker did, what was merged, and what's left.
    Merge to `dev` only when the user confirms.

---

## Worker spec template

Every spec must be self-contained (workers don't see this conversation):

```
Project: Agent Builder Platform (FastAPI + LangGraph). Read AGENTS.md first.
Epic <N>: <name>. Your task: <one sentence>.

Context: <relevant existing modules and what they do>
Contract (do not modify): <files + signatures>

Files you may create/edit: <explicit list>
Files you must NOT touch: contract files, anything outside the list.

Acceptance criteria:
- <criterion>
- <criterion>
- Tests added in backend/tests/ covering the above.

When done:
1. cd backend && uv run python -m unittest discover -s tests -v  (all pass)
2. git add -A && git commit -m "epic-<N>: <summary>"
3. Print a short summary of what you changed and any open questions.
```

---

## Rules for parallelism

- Parallelize **within** an epic by default. Epics are sequential.
- Only run two epics in parallel if the user asks AND EPICS.md shows no
  dependency between them (e.g. 10 and 11 are independent; 12 depends on 10).
- Never dispatch Alembic migrations to both workers at once. Only one
  migration per epic branch at a time; you own `alembic/versions` conflicts.
- If a task is too small or too coupled to split, give it to one worker.