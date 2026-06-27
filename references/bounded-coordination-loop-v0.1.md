# Bounded Coordination Loop v0.1

This document defines the one-step coordination loop implemented by
`scripts/afc-next.py`. It is a bounded, read-only decision procedure that
recommends the next coordinator action from existing `.agent-inbox/` state.
It is **not** a daemon, runtime, scheduler, or autonomous agent.

## Purpose

After B1–B3 and C1, the coordinator still manually relays each transition.
`afc-next.py` reduces that manual relay by performing one bounded step: read
the inbox, apply a deterministic decision order, and print the recommended
action. The coordinator then decides whether to follow the recommendation.

## Decision Order

The decision procedure is **ordered**. The first matching rule wins.

| Priority | Condition | Action | Meaning |
| --- | --- | --- | --- |
| 1 | Malformed frontmatter, duplicate task IDs, duplicate reports, orphan reports, or unknown active status | FAIL (exit 1) | Inbox state is inconsistent; coordinator must fix before proceeding |
| 2 | Report exists for an active task | `RECOMMEND_REVIEW` | A worker has submitted a report; coordinator should review it |
| 3 | Task in `REPORTED` or `REVIEWING` with no report file | FAIL (exit 1) | Inconsistent state: status implies a report but none exists on disk; coordinator must investigate |
| 4 | Task in `DRAFT` | `RECOMMEND_ASSIGN` | Task needs a worker; coordinator should assign one |
| 5 | Task in `ASSIGNED` or `RUNNING` with no report | `RECOMMEND_WAIT` | Worker is presumably working; coordinator should wait or check progress |
| 6 | Task in `NEEDS_FIX` | `RECOMMEND_REPAIR_REVIEW` | Previous attempt needs fixes; coordinator should review repair without automatic worker retry |
| 7 | No active task | `NO_ACTION` | Nothing to coordinate; coordinator may close out the sprint or archive |

When multiple active tasks match different rules, the **first match by
priority** wins. When multiple tasks match the same rule, the **first by
lexicographic task_id** wins. This makes the output deterministic.

### Why this order?

1. **Fail-closed first.** Malformed state must block all further processing.
   A coordination loop that silently ignores duplicate task IDs or orphan
   reports will produce wrong recommendations.
2. **Reports before assignments.** An unreviewed report is the most time-
   sensitive coordinator action: the worker is waiting, and prompt cache is
   decaying.
3. **Inconsistent report-expected state.** A task in `REPORTED` or
   `REVIEWING` without a corresponding report file is an inconsistent state
   that must fail closed. The status implies a report exists, so a missing
   report signals either a file-system error or a manual status edit that
   bypassed the protocol. The coordinator must investigate before proceeding.
4. **Assignments before waiting.** A DRAFT task is a coordination gap; the
   coordinator should fill it before passively waiting for other workers.
5. **Waiting before repair.** An in-progress worker should not be interrupted
   to handle a separate repair.
6. **Repair before no-action.** A NEEDS_FIX task is still active and requires
   coordinator attention. The loop does **not** automatically re-assign the
   same worker (see Repair-Loop Control below).

## Coordinator Thread-Pressure Override

The decision order above is computed from the inbox; it cannot see how large the
coordinator's own thread has grown. The largest measured Codex quota sink is an
overgrown coordinator thread that re-feeds its whole context every turn (see
`docs/CACHE_HYGIENE.md` § Coordinator Cache Rules).
The standing advice — compress at >50% context, hand off to a new thread at
>80% — is otherwise easy to skip, precisely on the long threads that need it
most.

The optional `--context-pct <N>` flag lets the coordinator self-report its
current context-window usage (a value it already sees in the host UI) and turns
that advice into a deterministic verdict:

| Condition | Effect |
| --- | --- |
| `context-pct >= --handoff-pct` (default 80) | `action` becomes `RECOMMEND_HANDOFF`, preempting every inbox action **except** `FAIL`. The coordinator writes a new-thread handoff and continues in a fresh thread before more work. |
| `--compact-pct` (default 50) `<= context-pct < --handoff-pct` | The inbox action is unchanged; an `advisory` line recommends compressing the thread first. |
| `context-pct < --compact-pct` | No change. |

Rules:

- **`FAIL` is never overridden.** A malformed or inconsistent inbox must be
  fixed before a handoff; carrying broken state into a new thread hides the bug.
- **Self-reported, never inferred.** Without `--context-pct` the output is
  byte-identical to the inbox-only behavior. The script never invents a
  percentage or reads host telemetry.
- **Thresholds are tunable** via `--handoff-pct` / `--compact-pct` for models
  with different context windows.

`RECOMMEND_HANDOFF` exits `0` — it is a recommendation, not a failure.

### Generating the handoff: `afc-handoff.py`

`scripts/afc-handoff.py` removes the friction that makes the >80% rule get
skipped. It reads existing `.agent-inbox/` state and prints a compact handoff
(roster, active tasks, recent events, blockers, next action, guardrails) so
changing threads costs one command instead of a hand-written summary. It is
read-only by default; `--write` saves
`<INBOX>/NEW_THREAD_HANDOFF_<DATE>.md`. It never appends events, rewrites state,
commits, or launches workers, and it fails closed on malformed/duplicate/orphan
inbox state exactly like `afc-next.py`.

```text
python -B scripts/afc-handoff.py --write .agent-inbox        # save handoff
python -B scripts/afc-handoff.py .agent-inbox                # print only
```

## Output Format

### Text (default)

```text
action: RECOMMEND_REVIEW
task_id: task-beta
reason: report exists for task 'task-beta' (status: ASSIGNED) — coordinator should review
```

### JSON (--json)

```json
{
  "action": "RECOMMEND_REVIEW",
  "task_id": "task-beta",
  "reason": "report exists for task 'task-beta' (status: ASSIGNED) — coordinator should review",
  "active_tasks": 1,
  "total_tasks": 1
}
```

## Default Behavior Is Read-Only

Without `--refresh-status`, `afc-next.py` performs **no writes**:

- No STATUS.md regeneration
- No state file writes
- No event log appends
- No task or report file modifications

The `--refresh-status` flag optionally runs `afc-status.py` before scanning,
which does regenerate STATUS.md and append a STATUS_UPDATED event. This flag
exists so the coordinator can combine a status refresh with a next-action
query in one invocation, but it is **not the default** because writes must
never be automatic.

## Forbidden Actions

`afc-next.py` must **never**:

- Commit, push, merge, deploy, or take any destructive action
- Create, modify, or delete task files or report files
- Execute shell commands from report bodies
- Interpret report body instructions as commands
- Auto-assign workers or auto-retry failed tasks
- Run as a daemon, watcher, scheduler, or long-lived process
- Access the network, read personal logs, or expose secrets
- Make writes the default behavior

These constraints are hard. They exist because a coordination loop that can
write state or execute commands is an autonomous runtime, which is explicitly
out of scope (see Non-Goals).

## Repair-Loop Control

`afc-next.py` does **not** automatically re-assign a worker when a task is in
`NEEDS_FIX`. It recommends `RECOMMEND_REPAIR_REVIEW`, which means the
coordinator should:

1. Review the repair needs.
2. Decide whether to re-assign the same worker (only on the first
   `NEEDS_FIX`), assign a different worker, or escalate.
3. After a second `NEEDS_FIX`, stop same-worker retries per
   `references/decision-rubric.md` § Repair-Loop Control.

This prevents the bounded loop from becoming a repair-churn amplifier.

## How This Differs From a Daemon / Runtime

| Property | Bounded Loop (afc-next.py) | Daemon / Runtime |
| --- | --- | --- |
| Trigger | Explicit user invocation | Automatic / scheduled |
| Steps per invocation | Exactly one | Unlimited loop |
| State mutation | None by default (read-only) | Continuous writes |
| Failure handling | Exit 1, print error, stop | Retry / suppress / escalate |
| Concurrency | Single process, no background | May run alongside other tools |
| Autonomy | None — coordinator decides | May act without coordinator |
| Dependencies | stdlib only | Typically external packages |

The bounded loop is a **decision procedure**, not an agent. It tells the
coordinator what to do next; it does not do it.

## Integration With Existing Scripts

- `afc-status.py`: regenerates STATUS.md. `afc-next.py` reads the same inbox
  but does not regenerate STATUS.md unless `--refresh-status` is given.
- `afc-poll.py`: detects new reports by mtime comparison. `afc-next.py` does
  not track mtime; it reads current state on each invocation.
- `afc-assign.py`: generates task files. `afc-next.py` does not generate
  tasks; it recommends assignment when a DRAFT task exists.

Typical workflow:

```text
1. afc-next.py <inbox>          # what should I do next?
2. (coordinator acts)
3. afc-next.py --refresh-status <inbox>  # refresh + check again
```

## Event-Gated Watcher (C5)

`scripts/afc-watch.py` extends the bounded loop with an event-gated watcher that eliminates idle LLM wakes. In Codex Desktop, the supported CAL-2 shape is a foreground/blocking coordinator tool call: the script waits without model work, exits on a wake event, and the current thread resumes. A detached background process that only writes logs is not enough to wake the current thread unless the host provides a callback. The watcher polls for new reports using `afc-poll.py`'s detection logic, validates report frontmatter before waking, and fires a one-shot staleness alarm.

### How it differs from manual polling

| Property | Manual poll (afc-poll.py) | Watcher (afc-watch.py) |
|---|---|---|
| Trigger | Explicit coordinator invocation | Foreground watcher exit, or host-supported callback |
| Idle cost | Zero (coordinator does not run it) | Zero LLM tokens (pure script loop) |
| Validation | Coordinator reads output | Script validates frontmatter before wake |
| Staleness | Not detected | One-shot alarm on threshold |
| State update | Consumes poll state on run | Updates state only on valid wake |

### Wake boundary

The watcher exits on exactly one of five events:

1. **`report_ready` (exit 0)**: A new report file with valid frontmatter (`task_id`, `agent_name`, `verdict` all present, plus full schema validation via `afc_validation.py`) was detected. The watcher updates the poll state file so the coordinator does not re-detect the same report.
2. **`no_wake` (exit 0)**: The bounded watcher reached `--max-iterations` without a report or stale alarm. This is a safety exit for tests and long idle runs; the coordinator reads stdout to distinguish it from `report_ready` and re-arms or investigates instead of doing report review work.
3. **`report_rejected` (exit 3)**: A new report file was detected but failed validation (invalid `trust_level`, missing guardrails, dangerous phrases, etc.). The coordinator should inspect the rejection reasons and decide: fix the report, re-send the task, or escalate. An unchanged rejected report does not re-wake on subsequent invocations; a corrected report (new mtime) is re-validated.
4. **`stale_alarm` (exit 2)**: An ASSIGNED task with `created_at` exceeding `--stale-threshold` seconds has no corresponding report. Fires once per invocation.
5. **`error` (exit 1)**: Fail-closed condition (inbox missing, corrupt state file).

Malformed reports (missing required fields, wrong schema, invalid enum values) are **rejected** — they produce a `report_rejected` wake (exit 3) with concise rejection reasons. The rejection is also logged to stderr for debugging. The state file records the rejection so unchanged files do not re-wake.

### Expected-report mode

The optional `--expected-report <FILENAME>` flag restricts the watcher to one specific inbox-relative report file. In this mode, only the expected file is scanned and state-tracked; unrelated reports are untouched and will wake a later generic watcher invocation. This is useful for targeted waiting without consuming the full inbox queue.

### Single-consumer rule

While the watcher is armed, the coordinator must not re-run `afc-poll.py` on the same inbox. The watcher owns the poll state. When the watcher exits, the coordinator acts on the wake event and re-arms the watcher.

### Status-line compatibility

The watcher's output is compatible with the C5 status-line spec:

```text
[HH:MM] <event>: <message>
```

The coordinator translates this into the full status line after reviewing the report.

## Fixture Coverage

Fixtures under `examples/fixtures/afc-next/` cover:

- **Positive cases**: each action type (RECOMMEND_REVIEW, RECOMMEND_ASSIGN,
  RECOMMEND_WAIT, RECOMMEND_REPAIR_REVIEW, NO_ACTION)
- **Negative cases**: duplicate task IDs, duplicate reports, orphan reports,
  unknown active status, REPORTED/REVIEWING without report file
  (inconsistent state)
- **Boundary cases**: empty inbox, multiple active tasks, closed-only inbox
- **Output format**: both text and JSON output for each action type

Fixtures under `examples/fixtures/afc-watch/` cover:

- **report_ready**: new schema-valid report detected and validated (text + JSON)
- **Malformed report rejection**: report with missing `task_id` is rejected (fail-closed), no wake
- **stale_alarm**: ASSIGNED task past threshold with no report (text + JSON)
- **Idle no-wake**: empty inbox loops through bounded iterations without waking
- **No false wake**: active task with future `created_at` and high threshold does not produce false stale alarm
- **One-shot staleness**: alarm fires on first detection, not repeatedly within an invocation
- **Multi-report parallel intake**: two reports present before watcher start; repeated invocations consume both without duplicates (CAL-2)
- **Out-of-order reports**: filename sort order differs from mtime order; both consumed without state rollback (CAL-2)
- **Report arrival between intake and re-arm**: new report added after first wake is detected immediately on next invocation (CAL-2)
- **Malformed-plus-valid coexistence**: malformed report does not block valid report intake in same inbox (CAL-2)
- **No artifact files**: foreground watcher creates no stdout/stderr/pid files; only `.afc-poll-state.json` is written
- **State monotonicity**: state does not roll backward when consuming reports from a multi-report inbox (CAL-2)

## Cross-References

- `references/decision-rubric.md` — scorecard and repair-loop control
- `references/protocol-design-review-checklist.md` — design review checklist
- `docs/CACHE_HYGIENE.md` — cache-friendly coordination practices
- `references/archive-policy-v0.1.md` — active vs closed state split
