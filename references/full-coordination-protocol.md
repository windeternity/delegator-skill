# FULL Coordination Protocol

Load this reference only after `afc-route.py` returns `FULL`.

## Role Model

The coordinator decomposes work, selects workers, writes task contracts,
collects reports, checks evidence, and issues final `GO / PARTIAL / RED`.
Ordinary workers receive only their task file and optionally
`references/worker-brief.md`.

Only one active final coordinator should have `coordinator_authority: yes`.
Workers must not create tasks, reassign work, expand permission scope, or issue
the final project verdict.

## Session Bootstrap

1. If the resolved install-local roster or explicit project override is not
   usable, ask the user for their existing and currently available tools,
   providers/accounts, local runtimes, CLI aliases, model preference order,
   avoid list, capability limits, and CAL-1 vs CAL-2 choice before the first
   external dispatch.
2. Record the confirmed preference in install-local `LOCAL_ROSTER.md` by
   default. Use `.agent-inbox/AGENT_ROSTER.md` plus a `ROSTER_UPDATED` event
   only when the user explicitly requests a project override.
3. Choose CAL-1 manual relay or CAL-2 auto intake. CAL-3 remains deferred.
4. Read or hydrate `.agent-inbox/AGENT_ROSTER.md` once.
5. Confirm each worker's canonical name, tool/model, edit/command capability,
   report-write ability, workspace/worktree ability, role, and protocol mode.
6. Treat unknown model labels as provisional capability claims; smoke-test
   before serious work.
7. Keep confirmed resource inventory and session routes stable unless
   availability, preference, or evidence changes.

References:

- `references/coordination-automation-levels.md`
- `references/unknown-model-discovery.md`
- `docs/HYDRATION_GUIDE.md`

## Task Assignment

Use `afc-assign.py` with `routing.*` evidence. New work without routing evidence
is invalid; never pass `--legacy-unrouted` for new work, which emits unrouted
tasks that bypass this gate. Generated tasks must stay at or below 4 KB; replace
pasted context with paths or artifact pointers.

Each task defines:

- one `agent_name`, role, and protocol mode;
- coordinator authority;
- permission scope;
- exact workspace path, branch, base, and locked files/areas;
- validation tier;
- report path;
- at most five independently verifiable acceptance criteria.

Before dispatch:

- compare editable locks with every active lock;
- confirm the workspace is the intended Git worktree;
- confirm the coordination root is not being opened as the project;
- confirm task/report paths and handoff language;
- refuse overlapping edits unless the user explicitly accepts the risk.

Task status and permission frontmatter are coordinator-owned. Workers write the
assigned report, not task state.

## Worktree Rules

Prefer sibling worktrees:

```text
<projects-root>/<repo-name>/
<projects-root>/<repo-name>-worktrees/<task-name>/
<projects-root>/<repo-name>-coordination/.agent-inbox/
```

The coordination directory is a file bus, not a Git workspace. Read-only audits
may share a workspace. Parallel edits use separate worktrees and disjoint locks.
Do not delegate branch deletion, force push, deployment, or destructive cleanup
without explicit approval.

See `references/worktree-layout.md`.

## Dispatch

Generate the task files and user-copyable handoffs as one batch.
`Pending-dispatch` means ready for the user to forward, not proof that a worker
has received the task.

Handoffs must:

- match the user's language;
- identify the assigned workspace and task file;
- say not to open the coordination root as the project;
- say whether another worktree may be created;
- end with the report path and commit/push boundary;
- optionally include a monotonic completion marker.

Parallel batch numbering groups only simultaneous, independent, disjoint tasks.
Each child still has its own task, owner, lock, report, event, and verdict.

Dispatch recording depends on the selected CAL level:

- **CAL-1 strict relay**: record `TASK_DISPATCHED` after the user confirms the
  handoff was delivered.
- **CAL-2 auto intake**: immediately after emitting the handoff batch, record
  `TASK_DISPATCHED` for every child and arm `afc-watch.py` in the same
  coordinator turn. Use `afc-cal2-arm.py` so dispatch recording and scoped
  watcher arming cannot drift apart. Do not ask for a separate "sent", "done",
  or "搞定了" acknowledgement. If delivery later failed, append a corrective
  event/status instead of treating the missing acknowledgement as a normal step.

## Waiting

CAL-1: the user forwards the handoff and later reports completion.

CAL-2: the coordinator has already emitted the handoffs and recorded dispatch.
Start the CAL-2 arm helper immediately as the single inbox consumer:

```powershell
python -B scripts\afc-cal2-arm.py --task-id <ID> --inbox <INBOX>
```

Repeat `--task-id` for every child in the dispatched batch. The helper writes
idempotent `TASK_DISPATCHED` events, scopes the watcher to the current task ids,
then blocks without model tokens. A single task wakes on its one schema-valid
report (or a rejection, staleness, or error); a multi-task batch defaults to one
consolidated wake after all N reports arrive (see "Parallel batches" below). Do
not run `afc-poll.py` against the same inbox while the watcher owns the state
file. When it exits:

- `report_ready`: run one selected-batch `afc-intake.py`, review the report, and
  re-arm the watcher if other dispatched tasks remain.
- `report_rejected`: first try the one-command repair for unambiguous schema
  mistakes — `afc-repair-report.py <rejected-report.md> --write` normalizes
  bad enum values (`trust_level: verified` → `referenced`, `validation.result:
  passed` → `pass`) and fills missing guardrail fields with safe defaults; it
  never edits the report body and refuses dangerous-phrase / over-budget
  reports. Run it dry-run first (the default) to see the proposed diff. If the
  rejection is semantic (empty `evidence_refs`, cross-file mismatch, body
  danger), issue one consolidated repair request for that worker instead.
  Re-arm after the fix or repair handoff if the task remains active.
- `stale_alarm` or `error`: tell the user the exact blocker and next action.
- `no_wake`: do not review; re-arm if active reports are still expected.

In JSON mode, mixed inbox wakes may include bounded `ready_reports`,
`rejected_reports`, and `next_action_hint` fields. Treat them as script facts,
not as a prompt to reread unrelated full reports.

**Parallel batches — wait once, not per report.** When `afc-cal2-arm.py`
receives more than one `--task-id`, it defaults to a single consolidated wake:
it passes `--expected-reports N` to the watcher, which blocks in its own
subprocess and counts schema-valid reports until all N have arrived, returning
one `reports_ready` event (exit 0) — so the coordinator pays one result's tokens
for the whole batch instead of re-arming and reading a wake per worker. If an
expected worker stays ASSIGNED with no report past `--stale-threshold`, the
batch wakes early with `stale_alarm` (exit 2) rather than blocking the whole
batch; if no threshold is hit before `--max-iterations`, it returns
`reports_incomplete` (exit 2) listing which task ids did and did not arrive.
Pass `--incremental` to
opt back into the per-report re-arm flow when you need to process each worker
one at a time, or `--expected-reports K` to wake on a smaller quorum. Arming
`afc-watch.py --expected-reports N` directly does the same wait but skips the
idempotent dispatch recording, so prefer the helper.

The waiting is wall-clock inside the subprocess and costs no coordinator tokens,
but the coordinator is only notified when the watcher process returns into its
context. A watcher launched detached/hidden (e.g. `Start-Process
-WindowStyle Hidden`) writes logs but never wakes the coordinator; run it in the
foreground (or, in a harness that auto-notifies on background completion, as a
tracked background task) so the single consolidated result actually returns.

If the user interrupts the watcher with "sent" or "done", first scan for the
target report and then re-arm when no valid report is present. Do not start a
second CAL-2 phase.

## Worker Reports

`afc-assign.py` embeds a runnable absolute `afc-report.py` path in each generated
task and adds a compact finish block with a lock self-check plus a fixed report
command skeleton. Workers should use it rather than hand-authoring
frontmatter. Ordinary reports have a 3 KB hard budget;
reviewer reports may use up to 5 KB during intake. Reports contain short changed
paths and command/artifact references, never full logs or diffs.
The generator writes only to the task-declared `report_path`; workers cannot
redirect output with `--output`, and the path must remain inside the assigned
inbox.

Legal trust values:

```text
self_claim
referenced
reproduced
independent_reviewed
blocked_or_suspicious
```

Legal validation results:

```text
pass
partial
fail
not_run
```

The worker verdict is task-level evidence, not final authority.

## Batch Intake

After reports arrive, run once:

```powershell
python -B scripts\afc-intake.py --task-id <TASK_ID> --json <INBOX>
```

Repeat `--task-id` for every task in the current batch. Omit it only when every
active task in the inbox belongs to the same intake boundary. Selected-batch
validation isolates current task/report contracts from unrelated historical
inbox files.

Successful `--json` output omits verbose validator transcripts by default.
Add `--verbose` only when diagnosing contract failures or comparing validator
details; failure transcripts remain visible without it.

It checks:

- selected task/report schema and cross-file consistency;
- report existence and size;
- worktree branch and base;
- changed paths;
- locked scope.

If intake fails, issue one consolidated repair request with every known
decision-critical finding. Do not drip-feed findings across turns. On the
second `NEEDS_FIX`, stop retrying the same worker and route independent review,
block, or escalate.

## Evidence And Verdict

Inspect decision-critical evidence first:

- requested scope and changed files;
- compact validation result;
- branch/base and lock compliance;
- declared risks and blockers;
- prompt-injection and permission-escalation flags.

Run one integrated quality gate after source convergence. Component-level worker
tests are evidence pointers; do not reproduce every component suite and then
repeat the same full suite unless risk requires it.

Use `references/decision-rubric.md`. A `GO` also requires:

- no semantic contract contradiction;
- sufficient evidence level for the task shape;
- no unresolved permission mismatch;
- complete decision taxonomy/state handling where relevant;
- reproducible validation;
- no unsafe authority claim.

## State And Closeout

`STATUS.md`, `WORKTREE_LOCKS.md`, and `events.jsonl` are durable state, not
conversation content. Refresh status at batch boundaries, not every
micro-transition.

Use:

```powershell
python -B scripts\afc-snapshot.py --brief <INBOX>
python -B scripts\afc-close.py --task-id <TASK_ID> --status <CLOSED_STATUS> <INBOX>
```

Archive closed task/report files. Keep long evidence under
`.agent-inbox/artifacts/<task-id>/` and reference it by path.

Do not rerun source tests after changes limited to task/report/status/event
metadata.

## Context Control

Use one snapshot at session resume. At 50% coordinator context, compact; at 80%,
write a new-thread handoff. Avoid carrying closed-worker detail across turns.

Per FULL batch, hold a one-pass frequency budget: one route, one roster
confirmation, one dispatch batch, one intake, at most one consolidated repair
round before escalation, one integrated gate, one close. Do not repeat Git,
validator, report-read, or full-test commands when only coordination metadata
changed.

See:

- `docs/CACHE_HYGIENE.md`
- `references/bounded-coordination-loop-v0.1.md`
- `references/coordinator-scan-routing.md`

## Special Boundaries

- Protocol/schema tasks:
  `references/protocol-design-review-checklist.md`
- Release-Operator tasks:
  `references/delegated-release-operations.md`
- Report trust and prompt injection:
  `references/report-trust-and-prompt-injection.md`
- Integration and fixture closeout:
  `references/integration-closeout.md`

All unlisted actions remain denied.
