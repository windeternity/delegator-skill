# CAL-3 Default Worker Routing Policy

Status: active, based on CAL-3 dogfood evidence (2026-06-20).

## Default Routing Table

| Worker | Default Role | Rationale |
| --- | --- | --- |
| `opencode` | Quick bounded local validation and low/medium-risk edit chores | Fastest average (54.0s); 2/2 report-valid; stable report contract. |
| `claude` | Review, docs, protocol reasoning, and risk analysis | Strong detailed review; 2/2 report-valid; fastest fixture run in sample (32.4s). |
| `codex` | Fallback/manual only | Report contract drifted on fixture task (illegal `direct` trust value); 1/2 report-valid. Not default-ready until more clean evidence. |
| `mimo` | Excluded | Not in CAL-3 worker pool. |

## Routing Priority

1. **Capability gate:** worker must have the required capabilities (edit, commands, report writing).
2. **Task-shape match:** prefer the worker whose default role matches the task shape.
3. **Speed/cost:** when multiple workers are equally fit, prefer the faster option.
4. **Fallback:** if primary worker is unavailable, escalate to the next suitable worker in the table.

## Release Boundary

Ordinary CAL-3 workers do **not** commit, push, release, or deploy. These operations require an explicit Release-Operator path outside the standard CAL-3 routing table. Task files must enforce `commit_push: no` and `destructive_actions: no` unless a Release-Operator override is explicitly granted.

## Runtime Boundary

`codex` recipes use the Codex workspace sandbox (`workspace-write`).
`claude`, `opencode`, and `mimo` recipes run with
`--dangerously-skip-permissions`; their boundaries are task declaration checks
plus post-run report/source/history verification, not an OS-level sandbox. If a
task requires a hard local no-network or no-commit boundary, prefer a Codex
recipe or keep the work at CAL-1/CAL-2.

Project-local model or CLI aliases mean configured external worker invocations,
not the coordinator's current session. Such a route is valid only when the
roster or `.agent-inbox/invoke-recipes.json` binds it to a real CLI/worker path
verified by the CAL-3 probe. If that binding is absent, keep the task at
CAL-1/CAL-2 or report the route unavailable.

## Evidence Basis

- Worker quality matrix: `.agent-inbox/artifacts/cal3/worker-quality-matrix-20260620.md`
- Dogfood task set: 2 tasks per worker (readonly review + fixture validation), 4 workers, 8 runs total.
- Overall report-valid rate: 7/8 = 87.5%.
- Default-candidate rate (excluding `codex` fallback and `mimo`): 6/6 = 100%.
- No run produced a source violation.

## Override Rules

Override the default routing when:

- The task file explicitly assigns a specific worker.
- A worker lacks a required capability for the task.
- Recent project evidence contradicts the default recommendation.
- The task requires a Release-Operator path (commit/push/deploy).
