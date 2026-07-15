# Session Bootstrap Gate

At the first Delegator activation in each coordinator session, the coordinator
runs one cheap CAL-default presence check before routing. The persisted choice
is install-local user-profile state, not per-thread or per-project state, so a
configured profile does not reopen onboarding.

The fuller resource/model/roster interview runs only before an external
dispatch when the resolved roster is missing, stale, contradicted, incomplete,
or explicitly changed. `DIRECT` never pays that full-read cost.

## Bootstrap Decision Flow

After the CAL presence check, route each task:

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

3. **If DIRECT**: briefly state why (one sentence) and do not create coordination artifacts unless the user explicitly insists. Never run the full resource/bootstrap interview before a `DIRECT` route.
4. **If DELEGATE**: proceed to startup alignment. If no usable resolved resource
   inventory and execution preferences are recorded yet, or if the roster is
   missing, placeholder-only, incomplete, or unmatched for the selected worker,
   the coordinator must ask the user before the first external dispatch.

## Startup Alignment

When delegation is chosen and no confirmed usable resolved preference exists, present one compact block covering:

```text
External Dispatch Bootstrap:
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
- Record these in the install-local roster, or as an explicit project override?
```

The user may adjust the available resources, CAL level, route, preferred
model/tool pair, fallback order, or avoid list before confirming. Once
confirmed, these preferences become the **resolved default**: install-local and
shared across projects unless the user explicitly selects a project override.
Reconfirm only when the user asks to change them, a selected worker becomes
unavailable, the roster conflicts with the current conversation, or the task
needs a capability not covered by the recorded preference.

## Preference Recording

Record the confirmed preference without changing schema:

- Write/update the install-local `LOCAL_ROSTER.md` in the Skill directory (the
  default source of truth, shared across projects). A project
  `.agent-inbox/AGENT_ROSTER.md` is written only as an explicit override.
- Include resource availability, preferred model order, avoid/unavailable
  routes, and any smoke-test status in that note when known.
- Do not record secrets, account identifiers, private API details, or unstable benchmark claims.

The recorded preference is a routing input, not an authority grant. Capability, safety, permission scope, worktree locks, and evidence requirements still override user preference when they conflict.

The roster is resolved by `afc_roster.resolve_roster`: explicit `--roster-file`
/ `AFC_ROSTER_FILE`, then a marked project override, then install-local
`LOCAL_ROSTER.md`, then (legacy fallback) an unmarked project roster only when
LOCAL is absent. A usable roster is required before external dispatch, but not
before routing. `DIRECT` tasks still stop after the cheap first-run CAL
presence check and must not hydrate the full roster.

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
| CAL Default Presence Check | First Delegator activation per coordinator session | Reuse or collect the install-local user-profile CAL default before routing |
| External Dispatch Bootstrap | Before external dispatch when the resolved roster is not usable | Align the resolved external-worker roster |
| Roster Gate (`SKILL.md`) | After LITE/FULL/CAL route, before handoff/task generation/dispatch | Confirm roster_status=usable |
| Delegation ROI Gate (`SKILL.md`) | Per task | Decide whether to delegate or execute directly |
| Delegation Granularity Bounds (H6) | Per task | Check lower bound, round budget, upper bound |

The cheap presence check runs once per coordinator session; it asks the user only
when the install-local profile has no recorded CAL default. The external
dispatch bootstrap runs only when the resolved roster is missing, stale,
contradicted, incomplete, or explicitly changed. The Roster Gate and Delegation
ROI Gate run **per task** as before. The bootstrap does not replace or weaken
any existing gate. The Roster Gate is a **hot-path precondition enforced inside
each dispatch script** (`afc-assign.py`, `afc-lite.py`, `afc-cal2-arm.py`,
`afc-cal3-dispatch.py`), not coordinator discretion — an unusable roster fails
closed before any task file, dispatch event, watcher, or CLI launch.

## Repeat-Work Budget

Onboarding and safety gates must not become recurring coordinator work. SKILL.md
keeps only the invariant; the allowed/forbidden list lives here.

Allowed recurring:

- one cheap `--check-only` presence check per session start;
- one `--roster-status` check only after routing selects external dispatch;
- a CAL-3 probe only when CAL-3 is selected and the binding/probe is missing,
  stale, changed, or previously failed.

Forbidden recurring:

- re-explaining the product or CAL modes after a default is recorded;
- running the full resource interview before `DIRECT`;
- asking the user to fully configure CAL-1/2/3 when one selected/default route
  suffices;
- reading full inbox history or report bodies only to gate dispatch;
- full CLI probes on every CAL-3 task when a valid binding is recorded;
- generating coordination artifacts merely to justify a `DIRECT` route.

## CAL Level Pre-Selection

At the first Delegator activation in each coordinator session, before any
routing, the coordinator runs this lightweight sequence:

1. Read the resolved roster (install-local `LOCAL_ROSTER.md` by default; or note
   it is absent). If a CAL default is already recorded, skip this step entirely
   — do not re-ask. Cheap presence check: `python -B scripts/afc-first-run-config.py --check-only` (exit 0 = configured, 1 = not). `--skill-root` is a test/dev override of the Skill root; do not point it at a project inbox.
2. If unrecorded, present a compact CAL-1/CAL-2/CAL-3 distinction and ask the
   user to pick a default:
   - **CAL-1** (manual relay): safe default, works with any worker, no watcher required.
   - **CAL-2** (auto intake): recommended when the coordinator host supports foreground watchers and the user wants reduced relay overhead.
   - **CAL-3** (full auto): the coordinator launches workers via a local CLI. Highest automation, highest risk; the first automatic dispatch still requires the CLI verification gate (`docs/FIRST_RUN.md` §4).
3. Record the choice in `LOCAL_ROSTER.md` SESSION PREFERENCES (no project
   `events.jsonl` is written). Scaffold from `templates/TEMPLATE_LOCAL_ROSTER.md`
   if the file does not exist.
4. If the user does not answer and work must proceed, use CAL-1 for that
   invocation only and leave the preference unrecorded.

This is the read-budget mechanism for initialization: the check runs once per
coordinator session, including sessions that route `DIRECT`; the orientation
and choice run only once per install-local user profile. After the check,
`DIRECT` tasks stop immediately as usual.

## CAL Level Selection

The install-local CAL default governs future coordination across projects until
the user changes it. An explicitly marked project roster may override it for
that project. CAL-1, CAL-2, and CAL-3 are valid recorded defaults, but recording
CAL-3 does not skip its dispatch gate: the first automatic dispatch still
requires the CLI verification prerequisites below and in `docs/FIRST_RUN.md`
§4.

## Mode-Dependent Resource Requirements

What the bootstrap must secure from the user depends on whether the coordinator
launches the worker itself. The deciding question is the relay vs auto-dispatch
distinction, not the model brand.

- **CAL-1 / CAL-2 (and LITE): the user is the transport.** The coordinator never
  invokes the worker programmatically — it emits handoff text the user forwards.
  The target may be an external chat, tool, model, CLI, IDE, or app session,
  including an unfamiliar model, but it must be recorded as an external roster
  route with permissions and report-writing expectations. A current-session
  subagent, built-in helper, internal `multi_agent` call, or chat-only call
  inside the coordinator runtime is never valid. A capability smoke test is
  optional (see `references/unknown-model-discovery.md`); there is **no CLI
  verification gate**.
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
