# Coordination Automation Levels (CAL)

This reference defines the user-selectable automation level for a Delegator coordination session. The level controls who relays task handoffs, who detects worker completion, and whether worker tools are launched automatically.

Choose whether to use AFC before choosing a CAL level. See
`references/coordination-routing-policy.md` for the upstream skill activation
and routing policy.

CAL is a session setting, not a schema version. It can be recorded in local notes, `STATUS.md` prose, or `events.jsonl` summaries, but it does not change the `agent-file-coordination/*` schemas.

CAL workers must be external to the current coordinator session. A built-in
subagent, `multi_agent.spawn_agent`, or chat-only worker call is not a CAL-1,
CAL-2, or CAL-3 worker route. Model or CLI aliases must resolve to an AFC
roster entry, a user-relayed external worker, or a CAL-3 CLI recipe.
If no such route exists, stop and report that the worker route is unavailable.

## Level Summary

| Level | Name | User relays task handoff | User reports worker completion | Coordinator auto-intakes reports | Coordinator auto-starts workers | Current posture |
|---|---|---:|---:|---:|---:|---|
| CAL-1 | Manual Relay | yes | yes | no | no | Supported and actively optimized |
| CAL-2 | Auto Intake | yes | no | yes | no | Supported and actively optimized |
| CAL-3 | Full Auto Coordination | no | no | yes | yes | Selectable default; CLI-verification-gated at dispatch |

## CAL-1: Manual Relay

The user acts as the relay:

1. The coordinator writes task files and gives the user short handoff text.
2. The user forwards the handoff to the worker.
3. The worker writes the report file.
4. The user tells the coordinator that the worker is done.
5. The coordinator verifies the report path and evidence before judging.

### Benefits

- Lowest operational risk.
- Works with any worker that can read a task file and write or return a report.
- No long-running coordinator watcher is required.
- Still removes most copy-paste load: the worker reads a task file instead of a long chat prompt, and report evidence lands in a structured file.

### Risks And Costs

- The user remains a relay and can forget to notify the coordinator.
- Coordination is slower.
- The coordinator must still reject chat-only completion claims when the report file or expected worktree artifacts are missing.

## CAL-2: Auto Intake

The user still relays the task handoff, but the coordinator detects completion:

1. The coordinator writes task files and gives the user short handoff text.
2. The coordinator records `TASK_DISPATCHED` on handoff emission, treating
   delivery as assumed. This is not proof of worker receipt; delivery failure
   is handled later as a corrective event.
3. In the same coordinator turn, the coordinator arms a single foreground
   watcher for the inbox. Use `afc-cal2-arm.py --task-id <ID> --inbox <INBOX>`
   for this combined record-and-arm step; the helper scopes the watcher to the
   current task/report or repeated current task IDs. It must not wait for the
   user to confirm "sent" or "done".
4. The user forwards the handoff to the worker while the watcher is armed.
5. The worker writes a schema-valid report file.
6. The watcher returns `report_ready`; the coordinator intakes, reviews, emits a status line, and prepares the next handoff.
7. When enabled with `--auto-archive`, the re-armed watcher archives at most one task whose coordinator-owned status is already terminal, then refreshes `STATUS.md` and exits.

CAL-2's out-of-box invariant is:

```text
handoff emitted -> TASK_DISPATCHED recorded -> afc-watch.py armed
```

These three actions are one coordinator operation. A fresh thread that is told
"use CAL-2" must not split them across user acknowledgements.

### Benefits

- Removes the user's "done" message.
- Waiting is handled by a zero-token script loop, not timer-driven LLM polling.
- Keeps worker launch under human control while reducing user interruption.
- Preserves visibility in the coordinator conversation.
- Can remove closed task/report files from the active inbox without automating verdict selection.

### Risks And Costs

- Requires a foreground watcher or an equivalent host-supported callback. A detached background process that only writes logs does not wake the current Codex Desktop thread.
- Long tool-call limits, quota limits, app restarts, computer sleep, or terminal interruption can stop the watcher.
- The inbox must have exactly one consumer. Do not run `afc-poll.py` while `afc-watch.py` owns the state file.
- The coordinator must distinguish `report_ready`, `stale_alarm`, `no_wake`, and `error` instead of treating every exit as completion.
- Automatic archive is opt-in and must fail closed on missing reports, duplicate/malformed state, or validation failure.
- If the user interrupts the watcher with a routine relay message, the
  coordinator scans for the expected report and re-arms if it is absent; it does
  not ask for another acknowledgement.

### Parallel Intake Semantics

CAL-2 treats an active inbox as an event queue, not as a single-task wait:

1. Multiple workers may be active at the same time.
2. Any schema-valid report may wake the coordinator, regardless of which task was expected next.
3. One watcher wake produces one coordinator intake turn.
4. After reviewing that report, the coordinator immediately re-arms the watcher until no new report remains.
5. New reports that land between watcher exit and re-arm must be detected on the next invocation.

The watcher must not lose or duplicate reports when workers finish out of order. State persistence must be monotonic: processing one report must not roll back the seen-state for reports that were already consumed, and it must not mark unseen reports as reviewed.

The per-report re-arm above is the incremental flow. For a parallel batch, `afc-cal2-arm.py` defaults instead to one consolidated wake after all N reports arrive (it passes `--expected-reports N` to the watcher), so the coordinator pays one intake turn for the whole batch; pass `--incremental` to choose the per-report flow when you want to process each worker as it finishes.

### CAL-2 Hardening Plan

Before considering CAL-3, CAL-2 must pass a parallel-intake dogfood round:

- multiple reports present before the watcher starts
- multiple workers finishing in quick succession
- report arriving between intake and re-arm
- filename order that places older and newer reports on opposite sides of the detected report
- malformed report plus valid report in the same inbox
- no default artifact logs for foreground watcher mode
- no stale `.tmp` files after successful state persistence
- low idle overhead with the default poll interval and a bounded active inbox

## CAL-3: Full Auto Coordination

The coordinator both starts workers and intakes reports. A dispatcher looks up a worker invocation recipe, launches the worker in the assigned workspace, captures logs, and continues the loop.

CAL-3 must launch real worker processes through `afc-cal3-probe.py` /
`afc-cal3-dispatch.py` or an equivalent documented CLI dispatcher. It must not
launch current-session subagents.

### Benefits

- Lowest user effort for large queues of low-risk, repeatable tasks.
- Can compress wall-clock time by removing both human relay points.
- Useful only after CAL-1 and CAL-2 are reliable, measurable, and economical.

### Risks And Costs

- Highest risk: a bad assignment, wrong workspace, wrong permission scope, or repeated bad fix can be amplified automatically.
- Worker stdout, reports, dependency output, and logs remain untrusted and may contain prompt-injection attempts.
- Headless workers cannot ask the user for mid-run approval unless the dispatcher implements a safe pause path.
- Commit, push, merge, deploy, destructive cleanup, secrets handling, and permission escalation must remain manual unless explicitly approved for the current project and action.
- Requires per-agent `invoke_command`, log capture, session identifiers, stop conditions, rework fuses, and visible status lines.

### Current Posture

CAL-3 may be recorded as a project default. It does not change the
`agent-file-coordination/*` schemas. Recording CAL-3 as a default is a
preference; it does not bypass the dispatch gate — before the first automatic
dispatch the coordinator must still satisfy the §4 CLI verification
prerequisites (callable CLI, recorded binding, probe + direct report
validation). The technical prerequisite from CAL-2 intake hardening is
satisfied; the product/value gate (collect external project evidence before
recommending CAL-3 broadly) remains, so CAL-3 is the higher-risk default and
should be chosen deliberately, not as a casual fallback.

The opt-in implementation shape is:

1. `afc-cal3-probe.py` detects local headless CLIs and writes project-local
   invoke recipe drafts under `.agent-inbox/`.
   Before dispatching a worker alias for the first time, confirm the effective
   CLI configuration behind that alias. For Codex-style workers, record the
   intended `CODEX_HOME` or equivalent environment, provider, endpoint class,
   model, and reasoning effort in the project-local recipe or roster. If that
   binding is absent or ambiguous, stop and ask; do not silently fall back to a
   default user profile.
2. `afc-cal3-dispatch.py` launches a task's configured worker with an argv list
   (`shell=False`), captures stdout/stderr to per-task artifacts, records
   `TASK_DISPATCHED` / `TASK_STARTED`, prints one visible coordinator status
   line per transition, waits for the worker process to exit, and validates the
   exact expected report path directly. Worker stdout is never completion
   evidence. `afc-cal2-arm.py` / `afc-watch.py` are then used only as a
   best-effort dashboard/intake compatibility path for reports that already
   exist. It refuses to auto-spawn after the configured rework fuse is reached
   (`--max-attempts`, default 2).
3. `afc-release-executor.py` handles deterministic post-GO commit/push chores
   behind the J6 Release-Operator hard gates when explicitly authorized.

Per-user codex backend: by default `afc-cal3-probe.py` resolves the newest
native `codex.exe` (its install dir carries a version hash that changes on
auto-update, so the recipe is rebuilt from the latest on each probe). To route
codex through a personal launcher instead -- e.g. a wrapper that selects a
third-party model and sets its `CODEX_HOME` / API key -- set
`AFC_CAL3_CODEX_LAUNCHER` to that script's path before probing; the recipe then
invokes it via `powershell -File` / `cmd /c`, keeping machine-specific paths and
credentials out of the recipe and the repo. After install/update, run
`afc-cal3-probe.py` once and check each codex probe's `backend` field
(`native` | `launcher`) to confirm which codex it will drive.

Default worker routing for CAL-3 dogfood is recorded in
`references/cal3-default-routing-policy.md`. It is evidence-based routing
guidance, not permission expansion: task permission scope and explicit
Release-Operator authorization still control what a worker may do.

CAL-3 permission profiles are dispatcher-side policy presets, not schema
extensions. `cal3-readonly` is source-readonly rather than filesystem-readonly:
workers may still need workspace write access to create the report, so the
dispatcher verifies after exit that no source files changed. Boundary
enforcement is worker-specific: `codex` recipes use the Codex workspace sandbox
(`workspace-write`), while `claude`, `opencode`, and `mimo` recipes run
headless with `--dangerously-skip-permissions` and are bounded by
task declaration checks, direct report validation, source/history post-run
guards, and coordinator review rather than an OS-level sandbox. For trusted
disposable or dedicated local workspaces, `cal3-local-autonomous-high` permits
bounded local source work, but destructive actions, network access, secrets
handling, commit/push, merge, deploy, or permission escalation still require a
separate explicit release/authorization path for that exact action.

The current project should continue optimizing CAL-1 and CAL-2 across:

- execution efficiency
- report quality
- coordinator token economy
- foreground watcher reliability
- recovery from watcher interruption
- parallel CAL-2 intake without lost or duplicate reports
- clear user-visible status and exception reporting

CAL-3 may be recorded as a project default when the user deliberately chooses
it, but it is the higher-risk default. Prefer CAL-1 or CAL-2 until CAL-3 has
been dogfooded and measured enough to show that automation reduces user burden
without increasing coordinator token cost or risk.

Promoting CAL-3 from a deliberate user choice to a broadly recommended default
requires recorded external-project evidence, not only local fixtures or
dogfood anecdotes. At minimum, record generated-task size, handoff size,
report-valid rate, repair round count, source/history violation rate, worker
configuration binding accuracy, user relay burden, and coordinator-token impact
across several projects before changing the recommendation posture.

## Choosing And Remembering A Level

The CAL level is chosen once, at the **first skill trigger** for a project,
before any routing or delegation. This is a lightweight step: the coordinator
presents a compact CAL-1/CAL-2/CAL-3 distinction and asks the user to pick a
default. The fuller resource/model/roster interview stays at the first external
dispatch (see `references/session-bootstrap-gate.md`), where it is actually
needed.

```text
Pick a default coordination level for this project:
- CAL-1 (manual relay): you forward handoffs and report done. Safe default, works everywhere.
- CAL-2 (auto intake): you forward handoffs; the coordinator auto-detects reports. Recommended when a foreground watcher is available.
- CAL-3 (full auto): the coordinator launches workers via a local CLI. Highest automation, highest risk; first dispatch still requires CLI verification.
I will record this as the default until you ask to change it.
```

After the user chooses, record the level in project-local coordination state:

- `.agent-inbox/AGENT_ROSTER.md`: add a short preference note near the top or
  in coordinator `Notes`.
- `.agent-inbox/events.jsonl`: append a `ROSTER_UPDATED` summary such as
  `Confirmed default CAL-2 auto intake` (or CAL-1 / CAL-3).

The recorded level becomes the default for future coordination on that project.
Do not ask again unless the user requests a change, the watcher or worker route
is unavailable, or the current task needs a capability outside the recorded
preference.

If the user does not choose and work must proceed, default to CAL-1 for that
invocation only and leave the project default unset.

CAL-3 may be recorded as a default. Recording it does not skip its dispatch
gate: the first automatic dispatch under CAL-3 still requires the CLI
verification prerequisites in the CAL-3 section above and `docs/FIRST_RUN.md`
§4.

## Switching Levels Mid-Task

The user may switch levels during a run.

- Downgrade immediately when requested. CAL-3 -> CAL-2 stops launching workers; CAL-2 -> CAL-1 stops the watcher and returns completion notification to the user.
- Upgrade only after checking prerequisites and explaining the additional risk.
- Existing task files remain valid. The coordinator changes only the relay/intake/dispatch behavior and records the switch in the local event log or status notes.
- Never use a level switch to bypass permission scope, worktree locks, report validation, or coordinator review.

## Status Visibility

All levels must keep the user informed in the coordinator conversation:

- assignment sent or ready to send
- watcher armed, interrupted, timed out, or errored
- report received and under review
- GO / PARTIAL / RED outcome
- blocked state requiring user decision

Every external-agent handoff should carry a session-level monotonic pending-dispatch label, for example `待派发.#01`, `待派发.#02`, `待派发.#03`. The sequence increments across all workers and must not reset per agent. The label is user-facing action state: the handoff is ready but the user still needs to forward it. This lets the user distinguish pending handoffs from already-delivered ones before CAL-2 arms a foreground watcher.

Automation removes waiting and repetitive relay work. It must not remove visibility, evidence review, or user control over high-risk actions.

## Parallel Dispatch Batch Numbering

When the coordinator emits multiple tasks simultaneously, batch numbering groups them under one main sequence number with child suffixes for visibility.

### Format

```text
待派发.#<BATCH>.<CHILD>    (Chinese)
Pending-dispatch: #<BATCH>.<CHILD>    (English)
```

Example: three parallel tasks get `待派发.#25.1`, `待派发.#25.2`, `待派发.#25.3`.

Serial or dependent tasks keep the ordinary `待派发.#<N>` format (no child suffix).

### Batch Eligibility

A batch is appropriate only when **all** of the following hold:

1. **Simultaneous emission.** The coordinator emits the handoffs in the same turn, not across multiple turns.
2. **Independence.** The tasks have no validation, review, authorization, or integration dependencies on each other.
3. **Disjoint editable locks.** Each task's `locked_files_or_areas` does not overlap with another task's editable locks. Read-only overlap (e.g., both tasks read `SKILL.md`) is safe.

If any condition fails, use ordinary serial `待派发.#<N>` labels.

### Each Child Is Independent

Despite the shared batch number, each child is a fully independent task:

- Separate task file (`task-<AGENT>-<name>.md`)
- Separate agent owner
- Separate lock entry in `WORKTREE_LOCKS.md`
- Separate report path
- Separate event log entries (`TASK_ASSIGNED`, `TASK_DISPATCHED`)
- Separate verdict

The batch number is a **user-facing grouping label**, not a shared lifecycle or ownership container.

### Corrections and Reassignments

- **Do not reuse an old child label.** If `待派发.#25.2` is cancelled or superseded, do not reassign `.2` to a new task.
- **Same active batch, semantically part of the wave.** If a correction or reassignment is semantically part of the same parallel wave (e.g., a replacement worker for the same subtask), assign the next unused child suffix within the same batch. Example: if `.1` and `.2` are active and `.2` needs replacement, assign `待派发.#25.3`.
- **New wave.** If the correction is a new independent task (not a replacement for a batch member), use a new top-level batch number.

### Examples

**Eligible batch (three independent docs tasks):**

```text
待派发.#25.1
发给: Implementer
为什么给它: docs-only task, independent locks
匹配度: fast docs agent
交接语: [fenced block]

待派发.#25.2
发给: Reviewer
为什么给它: independent review task, disjoint locks
匹配度: review-specialized agent
交接语: [fenced block]

待派发.#25.3
发给: Docs-Writer
为什么给它: independent docs task, read-only overlap only
匹配度: docs agent
交接语: [fenced block]
```

**Not a batch (dependent tasks):**

```text
待派发.#26
发给: Implementer
为什么给它: implementation must finish before review
匹配度: fast implementation agent
交接语: [fenced block]

待派发.#27
发给: Reviewer
为什么给它: review depends on #26 output
匹配度: review-specialized agent
交接语: [fenced block]
```

These are serial tasks, not a batch — #27 depends on #26's output.

### Relationship to CAL-2 Parallel Intake

Batch numbering is a handoff-label convention, not a watcher or intake mechanism change. CAL-2's parallel intake semantics (any schema-valid report wakes the coordinator, regardless of batch) remain unchanged. The batch number helps the user visually group concurrent handoffs; it does not affect report detection, ordering, or state persistence.
