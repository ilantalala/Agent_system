# Working rules — read this before doing anything else

This project exists so I (Ilan) can learn while building it. I know a
little FastAPI and not much more — treat every library, pattern, or tool
in this project as something I may not know yet, not just the ones
called out explicitly in the docs. Ask rather than assume.

## The core rule: I write the code, not you

Do not use file-editing tools to write or modify implementation code —
routes, models, business logic, prompts, graphs, components, anything
that's the actual point of the current story. Instead:

- Show me the code in your response as text, and tell me exactly which
  file it goes in and where.
- I will type or paste it in myself.
- Once I say I've added it, help me verify it (what command to run, what
  to check, what the output should look like).

Exceptions where using your tools directly is fine:
- Running commands I ask for — installs, migrations, starting servers,
  running tests.
- Reading or inspecting existing files to answer a question or help debug.
- Genuinely tool-generated artifacts I wasn't going to type anyway (e.g.
  an `alembic revision --autogenerate` migration, CLI scaffolding output)
  — that's tool output, not a lesson.

If you're unsure whether something counts as implementation code, ask me
first rather than guessing.

## Plan before you build

For every user story, in this order:
1. Briefly explain the concept it's built around, in plain terms, and
   confirm I understand before moving on — ask me, don't assume I do.
2. Propose a plan: which file(s), route/model/function/node, what it
   depends on, roughly how it fits together. Wait for my go-ahead before
   we start.
3. Walk me through writing it, one piece at a time, per the rule above.
4. Tell me how to verify it manually before we call the story done.

## Migration epics (moving existing code onto LangChain/LangGraph)

Some epics replace code I already wrote. For those, before step 2 above:
- Read the existing code for that feature and give me three lists: what
  we'll **port** (keep the logic, move it into the new structure), what
  we'll **replace**, and what we'll **delete**.
- Keep every existing endpoint's path and request/response shape, so the
  frontend keeps working. If a shape truly has to change, stop and tell
  me why first.
- Build the new version next to the old one, verify it, switch the route
  over, and only then delete the old code. I do the deleting, per the
  core rule.

## Libraries change — check, don't recall

LangGraph, LangChain and LiteLLM change their APIs often, and your memory
of them may be out of date.
- Before showing me code that uses them, check the installed version
  (`pip show <package>`) and confirm the import paths and function
  signatures exist in that version — by reading the installed source or
  the current docs.
- If what you remember and what's installed disagree, tell me which one
  you went with.

## Explaining framework concepts

When a story introduces a framework concept (a LangGraph node, edge,
reducer, checkpointer, `ToolNode`, an arq job…), first show what it would
look like in plain Python without the framework, then show the framework
version and what it adds. I want to know what the framework does for me,
not just how to call it.

## Stay in scope

- Work on one user story at a time, from the epic I've told you we're
  currently on. Don't jump ahead to a later epic or story to "save time"
  or "be thorough" — the ordering in `epics-and-user-stories.md` is
  deliberate.
- Don't introduce a library, pattern, or abstraction that isn't already
  named in the project docs without telling me first and explaining why.
- If a story turns out to depend on something from an earlier one we
  skipped or got wrong, stop and tell me — don't quietly patch around it.

## When I'm stuck

Default to a hint or a guiding question over the full answer. If I'm
still stuck after that, or I ask directly for the answer, give it to me —
but the first move should help me get there myself, not skip past it.

## Session & branch workflow

- These rules apply for the whole project regardless of which epic we're
  on. That's why they live here, in `CLAUDE.md` at the repo root — you
  read this automatically at the start of every session, so I don't have
  to re-explain it each time or keep one giant chat session alive.
- Each epic gets its own git branch, cut from `main` when we start it
  (e.g. `epic-6-langchain-models`). Tell me the branch name to create
  before we begin an epic's first story, if I haven't already made it.
- Two developers work on this project in parallel, each on their own
  epic branch. Before starting an epic, check in `epics-and-user-stories.md`
  that every epic it depends on is already merged to `main`; if not, stop
  and tell me.
- Don't merge a branch into `main` until I've told you that epic is done.