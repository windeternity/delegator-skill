# Task Intake & User Alignment

Before routing or coordinating, the coordinator must understand *what the user
actually wants*. This gate turns a vague or underspecified request into an
aligned, routable task. It runs **first** on a new request, before the
`SKILL.md` routing command — routing estimates (effort, workstreams, blast
radius) are only as reliable as your grasp of the request.

This gate aligns **task intent** (what to build, how far, within what limits).
It is distinct from `references/session-bootstrap-gate.md`, which aligns
**execution preferences** (CAL level, roster, worker models). Align intent
first; reuse recorded execution preferences without re-asking.

## Why align first

- A wrong assumption about goal or scope wastes a whole worker round: the worker
  executes the wrong task and writes a confident report for it.
- Routing inputs (`--estimated-direct-minutes`, `--independent-workstreams`,
  `--blast-radius`) are guesses until the task is understood.
- Permission and safety boundaries depend on knowing what the work touches.
- Silent assumptions surface late, as rework, instead of early, as one question.

## Alignment checklist

Confirm you can answer each item before routing. Pull answers from the
conversation first; only ask for what is genuinely missing or ambiguous.

| Item | Confirm | If unclear |
|---|---|---|
| Goal | The outcome the user wants, in one sentence | Ask "what does done look like?" |
| Scope | What is in scope and what is explicitly out | Propose a boundary, ask to confirm |
| Done-definition | How success is checked (tests, behavior, artifact) | Propose acceptance criteria |
| Constraints | Permissions, files/areas not to touch, deadline, environment | Ask before assuming any write/commit/network |
| Risk & reversibility | Blast radius, hard-to-undo actions | Default-deny; confirm before risky actions |
| Inputs/context | Repo, branch, workspace, relevant files | Confirm the intended workspace |

## Ask or assume

Do not ask about everything, and do not assume everything. Decide per gap.

**Ask the user first when a wrong guess would:**
- burn a worker round or a repair loop,
- cross a permission/safety boundary (commit, push, delete, network, secrets,
  production, dependency installs),
- be hard to reverse, or
- change the deliverable's shape (wrong feature, wrong file, wrong format).

**Assume a sensible default — and state it — when the gap is:**
- low-cost and reversible,
- covered by an obvious convention or recorded project default, or
- correctable next turn without wasted external work.

When you proceed on assumptions, make them visible: "Assuming X and Y — say so
if not." That lets the user correct course before any worker runs.

## How to ask

- **Batch the questions.** Ask everything you need in one compact block, not one
  question per turn. Drip-feeding questions is an anti-pattern.
- **Make each question answerable.** Offer 2–4 concrete options or a recommended
  default, not an open-ended "what do you want?".
- **Restate your understanding** of goal + scope in one or two lines and ask the
  user to confirm or correct it.
- **Match the user's language** (English / Chinese / etc.).
- **Keep it proportional.** A trivial request needs a one-line assumption, not an
  interview; a large, risky, or ambiguous request earns a real alignment round.

Compact alignment block:

```text
Before I route this, confirming I understand:
- Goal: <one sentence>
- In scope: <...>   Out of scope: <...>
- Done when: <acceptance check>
- Constraints: <permissions / files not to touch / deadline>
Open questions:
1. <question> (default: <recommended>)
2. <question> (options: A / B / C)
Confirm or correct, and I'll route from there.
```

## Anti-patterns

- Writing task files from a vague request without confirming goal or scope.
- Asking one question, waiting, asking the next — turning alignment into a slow
  interrogation.
- Re-asking what the conversation, roster, or recorded preferences already
  answer.
- Assuming a permission you were not granted, or re-asking for one you were.
- Hiding an assumption inside a task file instead of surfacing it to the user.

## After alignment

Routing comes first: it must precede any roster/inbox read, and a `DIRECT` task
must not create coordination artifacts (`SKILL.md` cost invariant). Do not write
durable state during or right after alignment.

- Hold the confirmed goal, scope, and constraints in working memory and run the
  routing command in `SKILL.md`.
- Only once routing selects a mode that needs artifacts (LITE/FULL) carry the
  confirmed intent into the task contract's Purpose, Non-Goals, Permission Scope,
  and Acceptance Criteria, and record any durable decision (task file, roster
  notes, or an `events.jsonl` summary). Never record secrets.
- For a `DIRECT` task, keep the alignment in the conversation and write no inbox
  state.

## Mid-task re-alignment

Re-open a short alignment round when:
- the user changes the goal or scope,
- a worker report reveals the request rested on a wrong assumption,
- a new constraint or risk appears, or
- routing returns `SPLIT` for ambiguity — reduce ambiguity *with the user*, then
  route again.

Do not silently expand or shrink scope mid-flight; confirm the change first.

## Relationship to other gates

| Gate | When | Aligns |
|---|---|---|
| Task Intake & Alignment (this) | New request, before routing | Task intent: goal, scope, done, constraints |
| Routing (`SKILL.md`) | After intent is clear | DIRECT / LITE / FULL / SPLIT |
| Session Bootstrap (`references/session-bootstrap-gate.md`) | First delegate decision per project | Execution preference: CAL, roster, models |
| Roster / ROI gates (`SKILL.md`) | Per task | Worker fit and delegation payoff |

## No schema changes

This gate is a coordinator-side decision protocol. It adds no frontmatter
fields, lifecycle states, or schema version bumps.
