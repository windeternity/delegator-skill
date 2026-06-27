# Archive Policy v0.1

This document defines the active-vs-closed split for `.agent-inbox/` and the
plain-file workflow that keeps the active inbox small. It is a policy-first
design with one optional one-task helper (`scripts/afc-close.py`) and an
explicit CAL-2 watcher trigger. It introduces no daemon and no schema change.

The goal is to make `.agent-inbox/` a working coordination workspace, not a
permanent dump. When the active inbox stays small, `STATUS.md` plus the
current active task and report can be the coordinator's default read target,
which is the central quota-saving lever.

## States

The task lifecycle states defined in
`references/task-report-schema.md` split cleanly into two groups. The split
is the single source of truth for the archive policy.

### Active (stay in `.agent-inbox/`)

These states are the live working set. Files in these states are read on
ordinary coordinator turns and must remain in the active inbox.

- `DRAFT`
- `ASSIGNED`
- `RUNNING`
- `REPORTED`
- `REVIEWING`
- `NEEDS_FIX`

### Closed (move to archive on closure)

These states are terminal. Files in these states leave the active inbox
once the coordinator verdict or supersede decision is recorded.

- `CLOSED_GO`
- `CLOSED_PARTIAL`
- `CLOSED_RED`
- `CANCELLED`
- `SUPERSEDED`

### Special case: `BLOCKED`

`BLOCKED` is **active and non-archivable** by default. A blocked task is
still live coordination state; archiving it would lose the reason for the
block and the conditions for unblocking.

`BLOCKED` only leaves the active inbox when the coordinator decides one of:

- the task is cancelled → move to `CANCELLED` and archive;
- the task is superseded by a new task → move to `SUPERSEDED` and archive;
- the work has already been merged under a different task ID → record the
  closure in `events.jsonl` and archive.

Never archive a `BLOCKED` task without recording the reason in
`events.jsonl` first.

## Default Coordinator Read Order

The coordinator's per-turn default read order, when the active inbox is
healthy, is:

1. `.agent-inbox/STATUS.md` — the summary table.
2. The current active task file (or Task Bundle) for the next action.
3. The matching worker report summary.
4. Compact evidence for the current task (validator summaries, failure
   fingerprints, artifact IDs).
5. Archived files or full artifacts **only when explicitly needed**.

This order exists so that on a quiet turn, steps 1-3 are enough. Steps 4
and 5 are deliberately behind an explicit need. See
`docs/CACHE_HYGIENE.md` § Coordinator Cache Rules for the cache mechanics
behind this ordering.

## Manual Archive Path

Closed task files and their matching report files move to a month-bucketed
archive directory under the active inbox:

```text
.agent-inbox/archive/<YYYY-MM>/
```

The path stays under the active inbox root so it is obvious where to look
when reconstructing historical context, and so it is automatically ignored
by the same `.gitignore` (or workspace exclusion) rules that protect
`.agent-inbox/` itself.

**Filename preservation rule (must hold):** every file moves under its
existing filename. The destination in the archive directory uses exactly
the same filename the file had in the active inbox. Operators do not
rename task, report, or verdict files when they archive them. Renaming
breaks the human audit chain and makes it harder to find a specific
closure when a user asks "what happened to task X last month?".

So if the source is `.agent-inbox/task-Implementer-c2.md` and the matching
report is `.agent-inbox/task-Implementer-c2-report.md`, the archive
destination for the **June 2026** bucket is:

```text
.agent-inbox/archive/2026-06/task-Implementer-c2.md
.agent-inbox/archive/2026-06/task-Implementer-c2-report.md
```

i.e. the same filenames, just one directory deeper. Any verdict file
moves under its own existing filename the same way.

## Heavy Artifacts

Long logs, full diffs, screenshots, recorded traces, and other bulky
artifacts do **not** live in the active inbox. They live in a separate
ignored directory and are referenced by `artifact_id` from reports and
verdicts.

Recommended location:

```text
.agent-inbox/artifacts/<task-id>/<artifact-id>.<ext>
```

- `artifacts/` is ignored by version control, just like `.agent-inbox/`.
- `artifacts/<task-id>/` keeps a task's artifacts together so they can be
  pruned as a unit.
- The `artifact_id` is a short, stable, human-readable token (for example
  `validate-2026-06-11.log`) that appears in `evidence_refs` and in
  `verdict.evidence_checked`.
- The coordinator reads **the artifact path** in ordinary review; opening
  the full artifact is an explicit Evidence Expansion step (see `docs/H3`
  / `H3` in the roadmap backlog), not a default behaviour.

Heavy artifacts are **outside the default coordinator context**. They are
read on demand, never on every turn.

## Filename Preservation (Restated)

A file may be moved; it may not be renamed. The destination in
`.agent-inbox/archive/<YYYY-MM>/` uses exactly the same filename the
file had in the active inbox. The original filename and `task_id` are
part of the audit chain; renaming a file during archive would silently
break that chain.

The only acceptable in-place change to an archived file is an optional
frontmatter field that records the closure date, such as
`closed_at: <YYYY-MM-DD>`. That field is **optional** in v0.1 and is
not enforced by the validator; it exists only when a coordinator finds
it useful for their own audit.

## events.jsonl Remains Append-Only

`events.jsonl` does not move. It is the append-only event log for the
whole inbox. The archive policy only governs task files, report files,
and verdict files.

When a file is moved to the archive, append a single `TASK_CLOSED` event
with the new path. Do not edit historical events; do not delete or rewrite
the log. Coordinator review uses compact event summaries, not a full log
re-read, per `docs/CACHE_HYGIENE.md` § Event Log and Status Board
Guidance.

## One-Task Workflow

The archive move remains a plain-file workflow. Sprint 19 adds
`scripts/afc-close.py` for exactly one task at a time. It preserves source
filenames, updates the task status to a terminal state, moves the task and
matching report files into `.agent-inbox/archive/<YYYY-MM>/`, and appends a
`TASK_CLOSED` event. Batch cleanup remains out of scope.

Dry-run first:

```text
python -B scripts/afc-close.py --dry-run --task-id <TASK_ID> --status CLOSED_GO .agent-inbox
```

Then run without `--dry-run` if the planned moves are correct:

```text
python -B scripts/afc-close.py --task-id <TASK_ID> --status CLOSED_GO .agent-inbox
```

The equivalent manual steps when a coordinator issues a closing verdict are:

1. Write the coordinator verdict file (or update `STATUS.md`).
2. Move the task file to
   `.agent-inbox/archive/<YYYY-MM>/`, **keeping its existing
   filename**. The destination filename equals the source filename;
   only the directory changes.
3. Move the matching report file to
   `.agent-inbox/archive/<YYYY-MM>/`, also under its existing
   filename. Do not rename it to match a template pattern.
4. Move heavy artifacts for that task to
   `.agent-inbox/artifacts/<task-id>/` (or leave a pointer if they are
   already there).
5. Append a `TASK_CLOSED` event to `.agent-inbox/events.jsonl` with
   the new path(s).
6. Re-run `scripts/afc-status.py` to regenerate `STATUS.md`. The
   summary table should no longer mention the closed task.

These steps are performed by a human, by the one-task helper, or by the
explicit watcher option below. They are never timer-triggered by a daemon.

### CAL-2 automatic trigger

After the coordinator has recorded a terminal task status, CAL-2 may opt in
to the same one-task workflow:

```text
python -B scripts/afc-watch.py --auto-archive .agent-inbox
```

The option is off by default and processes at most one task per invocation.
It requires a terminal task status, exactly one matching report, and a valid
active inbox before calling `afc-close.py`; it then refreshes `STATUS.md` and
validates the remaining active inbox. Missing reports, duplicate or malformed
state, validation failures, and `BLOCKED` tasks fail closed without an archive
move. The watcher does not choose a verdict or launch a worker.

## Rollback Guidance

The archive policy is reversible by design. A common reason to roll back
is that a `CLOSED_GO` task is reopened because the change had to be
revised.

To roll back a closure:

1. Move the task file and its report file from
   `.agent-inbox/archive/<YYYY-MM>/` back to `.agent-inbox/`.
2. Update the task frontmatter `status` from a `CLOSED_*` / `CANCELLED`
   / `SUPERSEDED` value to `NEEDS_FIX` (or `ASSIGNED` if it must be
   reassigned to a new worker).
3. Update the status board (`STATUS.md`) to reflect the new state, or
   re-run `scripts/afc-status.py`.
4. Append a `TASK_ASSIGNED` or coordinator comment event to
   `events.jsonl` with a short reason for the reopen.

A reopened task keeps its original `task_id`. Do not assign a new ID;
that would split the audit history in two.

For `BLOCKED` tasks that turn out to be misclassified, the same rollback
applies, except the new `status` is `NEEDS_FIX` rather than a
`CLOSED_*` value.

## What This Policy Does Not Do

To make the scope explicit:

- It does **not** add batch archive automation, a daemon, or an implicit hook.
- It does **not** change the task or report schema.
- It does **not** change the existing `agent-file-coordination/*`
  schema identifiers.
- It does **not** add a new validator rule that fails on a healthy
  active inbox.
- It does **not** require any new field in `STATUS.md`,
  `WORKTREE_LOCKS.md`, or `events.jsonl`.

Anything that goes beyond this list belongs in a separate backlog item,
not a follow-up edit to this document.

## Cross-References

- `docs/CACHE_HYGIENE.md` — cache mechanics that motivate the active
  inbox staying small.
- `references/task-report-schema.md` — canonical list of lifecycle
  states and schema identifiers.
- `SKILL.md` — coordinator workflow that consumes this policy.
