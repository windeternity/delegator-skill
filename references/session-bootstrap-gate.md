# Session Bootstrap Gate

On the first Delegator invocation in a conversation thread, the coordinator runs
a one-time bootstrap before writing any task files or dispatching any workers.
This gate decides whether delegation is worthwhile and aligns the user's
resource inventory, execution-model preferences, and fixed session routing
roster.

The CAL level is chosen separately and earlier, at the **first skill trigger**
for a project (see "CAL Level Pre-Selection" below), so the coordinator knows
the project default before any routing decision. The resource/model/roster
interview in this gate runs only at the first external dispatch, where it is
actually needed.

## Bootstrap Decision Flow

On the first Delegator invocation:

1. **Read the project roadmap** (e.g., `docs/ROADMAP.md`) if present. If absent, evaluate the user's requested work directly from the conversation.
2. **Decide DIRECT vs DELEGATE** using the following criteria:

| Factor | Favors DIRECT | Favors DELEGATE |
|--------|---------------|-----------------|
| Coordinator-token cost | Task is trivial; handoff+report overhead exceeds direct execution | Task is long-running or repeated; delegation amortizes overhead |
| Ceremony cost | Writing a task file + handoff + report review adds no value | Bounded scope + structured evidence improves quality |
| Task duration | Minutes of coordinator time | Hours of worker time |
| Parallelism | Single sequential step | Multiple independent steps that can run in parallel |
| Review depth | No review needed | Independent review adds real value |
| Repeated-loop needs | One-shot fix | Iterative fix-verify cycles benefit from worker isolation |

3. **If DIRECT**: briefly state why (one sentence) and do not create coordination artifacts unless the user explicitly insists.
4. **If DELEGATE**: proceed to startup alignment. If no project-local resource
   inventory and execution preferences are recorded yet, the coordinator must
   ask the user before the first external dispatch.

## Startup Alignment

When delegation is chosen and no confirmed project-local preference exists, present one compact block covering:

```text
Session Bootstrap:
- Existing resources: <tools/models/accounts/runtimes the user already has>
- Available now: <usable workers, providers, CLI aliases, local runtimes, paused routes>
- Execution preference: <preferred coordinator / worker tool-model pairs, avoid list, special constraints>
- Model preference order: <preferred models and fallbacks, including avoid list>
- CAL level: <CAL-1 | CAL-2 | CAL-3>  (default already chosen at first trigger; confirm or change here. CAL-2 recommended with a foreground watcher; CAL-1 for maximum manual control; CAL-3 only if its §4 CLI verification gate has been or will be satisfied before first dispatch)
- Proposed routes:
  - implementer: <Agent Name> / <Model> — code edits, tests, fixtures
  - docs: <Agent Name> / <Model> — documentation, references, templates
  - reviewer: <Agent Name> / <Model> — independent review, guardrail audit
  - fallback: <Agent Name> / <Model> — overflow or specialized tasks
  - paused/unavailable: <Agent Name> (reason) — excluded from assignment
- Record these as this project's default until you ask to change them?
```

The user may adjust the available resources, CAL level, route, preferred
model/tool pair, fallback order, or avoid list before confirming. Once
confirmed, these preferences become the **project-local default** and are not
re-litigated on every task or thread. Reconfirm only when the user asks to
change them, a selected worker becomes unavailable, the roster conflicts with
the current conversation, or the requested task needs a capability not covered
by the recorded preference.

## Preference Recording

Record the confirmed preference without changing schema:

- Add or update a short local preference note in `.agent-inbox/AGENT_ROSTER.md` near the top of the file, or in the relevant roster row `Notes` cells.
- Include resource availability, preferred model order, avoid/unavailable
  routes, and any smoke-test status in that note when known.
- Append a `ROSTER_UPDATED` event to `.agent-inbox/events.jsonl` summarizing the CAL level, resource inventory, and execution-model preference.
- Do not record secrets, account identifiers, private API details, or unstable benchmark claims.

The recorded preference is a routing input, not an authority grant. Capability, safety, permission scope, worktree locks, and evidence requirements still override user preference when they conflict.

## User Confirmation Gate

User confirmation is required before the first external dispatch **unless** the
same invocation already explicitly names the CAL level, acceptable
agents/models, and relevant available resources (e.g., "use CAL-2; use Agent X
for implementation"). In that case, the coordinator records those preferences
and may proceed without a separate confirmation round.

## Mid-Session Worker Replacement

The user may replace an agent or model mid-session:

- **Future tasks** use the replacement immediately.
- **Active tasks** continue with the original agent unless the user explicitly supersedes or reassigns them.
- **Reassignment preserves**: task history, monotonic dispatch numbering, worktree locks, and report-path clarity.
- The coordinator records the replacement in the event log (`ROSTER_UPDATED` or a status note) and does not re-open the full startup alignment.

## Relationship to Existing Gates

| Gate | When | Purpose |
|------|------|---------|
| Session Bootstrap Gate (this document) | First Delegator invocation per thread | Decide DIRECT vs DELEGATE; align session routing roster |
| Roster Gate (`SKILL.md`) | Before first task assignment | Confirm agent roster is current |
| Delegation ROI Gate (`SKILL.md`) | Per task | Decide whether to delegate or execute directly |
| Delegation Granularity Bounds (H6) | Per task | Check lower bound, round budget, upper bound |

The Session Bootstrap Gate runs at first use for a project and again only when recorded preferences are missing, stale, contradicted, or explicitly changed by the user. The Roster Gate and Delegation ROI Gate run **per task** as before. The bootstrap does not replace or weaken any existing gate.

## CAL Level Pre-Selection

At the first skill trigger for a project, before any routing, the coordinator
runs a one-time lightweight step when no CAL default is recorded:

1. Read `.agent-inbox/AGENT_ROSTER.md` (or note the file is absent). If a CAL
   default is already recorded, skip this step entirely — do not re-ask.
   Cheap presence check: `python -B scripts/afc-first-run-config.py --inbox
   <DIR> --check-only` (exit 0 = configured, 1 = not).
2. If unrecorded, present a compact CAL-1/CAL-2/CAL-3 distinction and ask the
   user to pick a default:
   - **CAL-1** (manual relay): safe default, works with any worker, no watcher required.
   - **CAL-2** (auto intake): recommended when the coordinator host supports foreground watchers and the user wants reduced relay overhead.
   - **CAL-3** (full auto): the coordinator launches workers via a local CLI. Highest automation, highest risk; the first automatic dispatch still requires the CLI verification gate (`docs/FIRST_RUN.md` §4).
3. If `.agent-inbox/` is absent, run `afc-init` once to create the scaffold,
   then record. Record the choice in `AGENT_ROSTER.md` SESSION PREFERENCES and
   append a `ROSTER_UPDATED` event to `events.jsonl`.
4. If the user does not answer and work must proceed, use CAL-1 for that
   invocation only and leave the preference unrecorded.

This pre-selection is the read-budget mechanism for initialization: one cheap
presence check skips the whole interview on every later invocation. It runs
once per project regardless of routing outcome (including DIRECT); after it,
DIRECT tasks stop immediately as usual.

## CAL Level Selection

The recorded CAL default governs future coordination for the project until the
user changes it, the watcher/worker route is unavailable, or a task needs a
capability outside the recorded preference. CAL-1, CAL-2, and CAL-3 are all
valid recorded defaults. Recording CAL-3 does not skip its dispatch gate: the
first automatic dispatch under CAL-3 still requires the CLI verification
prerequisites in "Mode-Dependent Resource Requirements" and `docs/FIRST_RUN.md`
§4.

## Mode-Dependent Resource Requirements

What the bootstrap must secure from the user depends on whether the coordinator
launches the worker itself. The deciding question is the relay vs auto-dispatch
distinction, not the model brand.

- **CAL-1 / CAL-2 (and LITE): the user is the transport.** The coordinator never
  invokes the worker programmatically — it emits handoff text the user forwards.
  Any model, account, or even a chat-only worker is acceptable, including
  unknown models, because the agent only needs a label to address the handoff
  to. A capability smoke test is optional (see
  `references/unknown-model-discovery.md`); there is **no CLI verification gate**.
- **CAL-3: the coordinator runs a process on the user's machine.** Before the
  first automatic dispatch the bootstrap must confirm a **callable** Agent/CLI
  per worker alias, record its exact invoke binding (environment/home, provider,
  endpoint class, model, reasoning effort — never secrets), and **verify** it
  via `afc-cal3-probe.py` plus direct report-path validation in
  `afc-cal3-dispatch.py`. Stdout is never completion evidence. A missing or
  ambiguous binding stops the run rather than falling back to a default profile.

The new-user walkthrough of this distinction is `docs/FIRST_RUN.md`.

## No Schema Changes

This gate does not add frontmatter fields, lifecycle states, or schema version bumps. It is a coordinator-side decision protocol documented as an on-demand reference.
