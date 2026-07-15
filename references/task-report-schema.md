# Task and Report Schema Reference

This protocol uses Markdown for readability, but task and report files should expose a small machine-checkable metadata block when the workflow is non-trivial.

Use YAML frontmatter at the top of task and report files, or an equivalent structured section if the agent cannot write frontmatter reliably.

## Task Metadata Schema

```yaml
---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: <short-stable-id>
agent_name: <Agent Name>
role: coordinator | planner | implementer | reviewer | smoke | docs | research | other
protocol_mode: full-skill | worker-brief | task-only | manual-paste | unknown
coordinator_authority: yes | no | limited
routing_decision: FULL
coordination_mode: delegate_full | moa_review | moa_design | moa_patch | moa_synthesis
comparison_group: <optional-stable-comparison-id>
status: DRAFT | ASSIGNED | RUNNING | REPORTED | REVIEWING | NEEDS_FIX | CLOSED_GO | CLOSED_PARTIAL | CLOSED_RED | BLOCKED | CANCELLED | SUPERSEDED
permission_scope:
  read_files: yes
  write_reports: yes
  write_task_files: no
  modify_source: no
  run_commands: none | read_only | tests_only | bounded
  network_access: none | docs_only | allowed
  commit_push: no | ask | approved
  destructive_actions: no
workspace:
  mode: read_only_shared | existing_edit_worktree | dedicated_worktree_required | manual_worktree_needed
  path: <absolute-or-project-relative-path>
  may_create_worktree: yes | no | ask
validation_tier: no-test-needed | targeted-test | smoke-test | browser-test | full-suite | production-replay
validation_command: <optional single-line code gate, e.g. python -m pytest tests/foo.py>
report_path: <PROJECT_ROOT>/.agent-inbox/<report-file>.md
report_tool: <absolute path to afc-report.py>
completion_marker: <optional exact final chat marker, e.g. Completed task: #37>
created_at: <YYYY-MM-DD>
source_artifacts:
  - <optional-upstream-doc-or-artifact-path>
moa:
  layer: candidate | synthesis
  decision_surface: <optional-shared-decision-surface>
---
```

Worker tasks must include a body section named `## Role Boundary` that states the worker is not the coordinator and must not create tasks, reassign work, approve final `GO / PARTIAL / RED`, or expand permission scope.

For ordinary workers, use `protocol_mode: task-only` or `protocol_mode: worker-brief` by default and `coordinator_authority: no`. Only a coordinator using `protocol_mode: full-skill` may declare `coordinator_authority: yes`.

`write_reports` authorizes writing only the specified `report_path`. `write_task_files` authorizes creating or modifying task files and should normally be `no` for workers.

`completion_marker` is optional user-visible coordination metadata. It records the exact expected final chat line when a handoff sequence is used; it never replaces the schema-valid report artifact. When the coordinator does not supply `handoff.sequence`, `afc-assign.py` reserves the next unique number from the inbox counter file `.agent-inbox/.seq` under an exclusive lock (an O(1) operation, never archived), so concurrent assignments cannot receive the same marker. Dry-runs do not consume a number. A real assignment that fails after reservation may leave a harmless gap; uniqueness and fail-closed counter persistence take precedence over gap-free numbering.

`validation_command` is an optional single-line code-quality gate authored by the coordinator (workers cannot write task files, so it stays trusted). When present, the handoff instructs the worker to run it as a gate before reporting — it must exit 0, and the worker records the command, exit code, and a short output tail in evidence. The worker self-run keeps cost proportionate; the command's scope is sized to `validation_tier` (run the targeted tests, not the whole suite). For genuinely high-risk tasks only — `permission_scope.commit_push: approved`, or `validation_tier` of `full-suite` / `production-replay` — `afc-intake.py` re-runs the command first-hand against the worker's diff and raises `VALIDATION_COMMAND_FAILED` on a non-zero exit, so code quality does not depend on the worker's honesty. This graded re-run is a deterministic function of existing task fields (never an LLM risk score); all other tasks trust the worker's evidence. Pass `--skip-validation-command` to disable the re-run.

`coordination_mode`, `comparison_group`, `source_artifacts`, and `moa` are optional
coordination metadata. They keep MOA candidate and synthesis tasks tied to the
same decision surface without changing the binding route enum. `routing_decision`
still records the deterministic route (`FULL` for coordinated work), while
`coordination_mode` describes the shape inside that route. See
`references/moa-coordination-modes.md`, `references/source-artifacts.md`, and
`references/moa-synthesis-rubric.md`.

## Task Body Template

Task files should expose role and authority both in metadata and in readable body sections:

```markdown
# Task - <Agent Name> <Task Title>

## Agent
<Agent Name>

## Role
coordinator / planner / implementer / reviewer / smoke / docs / research / other

## Protocol Mode
full-skill / worker-brief / task-only / manual-paste / unknown

## Coordinator Authority
yes / no / limited

## Role Boundary
You are the assigned worker agent for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.

## Permission Scope
Mirror the YAML frontmatter permission scope in human-readable form.

## Report Path
<PROJECT_ROOT>/.agent-inbox/<report-file>.md
```

Coordinator tasks may replace `## Role Boundary` with a section that states the coordinator limits, but ordinary worker tasks should keep the worker boundary text.

## Roster Schema

Before assigning external agents, establish the current project's roster. This is a hard gate unless the user already provided enough current model/tool/capability information in the conversation.

Roster files can be validated with YAML frontmatter plus a Markdown table:

```yaml
---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---
```

Required table columns:

```markdown
| Agent Name | Role | Tool | Model | Protocol Mode | Coordinator Authority | Worktree Capability |
| --- | --- | --- | --- | --- | --- | --- |
```

Recommended public-safe columns:

```markdown
| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

`Role`, `Protocol Mode`, and `Coordinator Authority` use the same value sets as task metadata. A roster must declare exactly one coordinator with `Coordinator Authority: yes`.

Reusable source docs should keep roster examples generic. Private local agent/model rosters belong in an installed local profile or a project-local `.agent-inbox/AGENT_ROSTER.md`, not in public examples, fixtures, or reports.

Project-local rosters may also carry the user's confirmed default CAL level,
available-resource inventory, model preference order, avoid/unavailable routes,
smoke-test status, and execution-model preference as a Markdown comment near
the top of the file or in row `Notes`. This is local coordination state, not a
schema field. If no resource inventory or preference is recorded, the
coordinator must ask before the first external dispatch and append a
`ROSTER_UPDATED` event after confirmation.

## Status Board Schema

Project-local status boards summarize active coordination state without requiring the coordinator to reread every task and report file.

Recommended path:

```text
<PROJECT_ROOT>/.agent-inbox/STATUS.md
```

```yaml
---
schema: agent-file-coordination/status-board
schema_version: 0.1.0
updated_at: <YYYY-MM-DD>
---
```

Required table columns:

```markdown
| task_id | assigned_agent | role | protocol_mode | status | workspace | report_path | next_action |
| --- | --- | --- | --- | --- | --- | --- | --- |
```

`role`, `protocol_mode`, and `status` use the same value sets as task metadata. `next_action` is coordinator-owned state such as `wait_for_report`, `coordinator_review`, `needs_fix_task`, or `close_task`.

## Worktree Locks Schema

Project-local worktree locks record which agent owns which worktree or file area during a milestone.

Recommended path:

```text
<PROJECT_ROOT>/.agent-inbox/WORKTREE_LOCKS.md
```

```yaml
---
schema: agent-file-coordination/worktree-locks
schema_version: 0.1.0
updated_at: <YYYY-MM-DD>
---
```

Required table columns:

```markdown
| lock_id | task_id | owner_agent | workspace_mode | worktree_path | branch | locked_files_or_areas | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
```

`workspace_mode` uses the same value set as task metadata. Lock `status` must be `ACTIVE`, `RELEASED`, `BLOCKED`, `STALE`, or `SUPERSEDED`.

Reusable examples should use placeholders such as `<PROJECT_ROOT>` and `<PROJECT_ROOT>-worktrees/<task-name>`, not real private paths.

## Event Log Schema

Project-local event logs record append-only coordination events. Use JSON Lines so a future CLI or watch mode can append one event without rewriting Markdown files.

Recommended path:

```text
<PROJECT_ROOT>/.agent-inbox/events.jsonl
```

Each non-empty line must be one JSON object:

```json
{"schema":"agent-file-coordination/event","schema_version":"0.1.0","event_id":"evt-001","event_type":"TASK_ASSIGNED","task_id":"task-reviewer-guardrail-audit","agent_name":"Reviewer","status":"ASSIGNED","created_at":"<YYYY-MM-DD>","summary":"Assigned Reviewer guardrail audit task."}
```

Required fields:

- `schema`: must be `agent-file-coordination/event`
- `schema_version`
- `event_id`
- `event_type`
- `created_at`
- `summary`

Allowed `event_type` values:

```text
ROSTER_UPDATED
TASK_CREATED
TASK_ASSIGNED
TASK_DISPATCHED
TASK_STARTED
WORKER_HEARTBEAT
TASK_ABORTED
REPORT_RECEIVED
REPORT_REJECTED
STATUS_UPDATED
WORKTREE_LOCKED
WORKTREE_RELEASED
COORDINATOR_VERDICT
TASK_CLOSED
TASK_BLOCKED
TASK_SUPERSEDED
REPAIR_ROUND
```

Task-related events should include `task_id`. If `status` is present, it must use the task lifecycle status values. If `lock_status` is present, it must use worktree lock status values.

CAL-3 `TASK_STARTED`, `WORKER_HEARTBEAT`, and `TASK_ABORTED` events include a
positive `attempt` number and `worker_session_id`. A timeout is recorded as
`TASK_ABORTED` with `abort_reason: timeout`; retrying never removes the earlier
attempt from append-only history. Heartbeats are liveness evidence only and do
not prove completion.

## Report Metadata Schema

```yaml
---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: <matching-task-id>
agent_name: <Agent Name>
verdict: GO | PARTIAL | RED
coordination_mode: delegate_full | moa_review | moa_design | moa_patch | moa_synthesis
comparison_group: <optional-stable-comparison-id>
changed_files:
  - <path or none>
evidence_refs:
  - <file/command/log/screenshot ref>
evidence_trust:
  trust_level: self_claim | referenced | reproduced | independent_reviewed | blocked_or_suspicious
  untrusted_inputs_seen: yes | no
  prompt_injection_suspected: yes | no
  permission_escalation_requested: yes | no
guardrails:
  role_boundary_followed: yes
  coordinator_verdict_given: no
  permission_scope_expanded: no
  secrets_private_data_printed: no
  production_default_behavior_changed: no
  commit_push_done: no
  destructive_command_done: no
validation:
  tier: no-test-needed | targeted-test | smoke-test | browser-test | full-suite | production-replay
  result: pass | partial | fail | not_run
reported_at: <YYYY-MM-DD>
---
```

Report `coordination_mode` and `comparison_group` should mirror the assigned
task when present. They are not authority fields; the coordinator still evaluates
the report through the decision rubric and final verdict schema.

## Coordinator Verdict Metadata Schema

```yaml
---
schema: agent-file-coordination/coordinator-verdict
schema_version: 0.1.0
task_id: <matching-task-id>
verdict: GO | PARTIAL | RED
score: <0-14>
score_breakdown:
  scope_control: <0-2>
  evidence_quality: <0-2>
  validation: <0-2>
  safety_privacy: <0-2>
  reproducibility: <0-2>
  conflict_awareness: <0-2>
  prompt_injection_resistance: <0-2>
evidence_checked:
  - <file/command/report ref>
blockers:
  - <none or blocker>
follow_up:
  - <none or next task>
reviewed_at: <YYYY-MM-DD>
---
```

## Minimal Validation Rules

A coordinator should mark the task `PARTIAL` or `RED` if:

- task/report `agent_name` does not match
- report `task_id` does not match the assigned task
- report omits guardrail confirmation
- worker task omits `## Role Boundary`
- worker task expects a report but does not grant `write_reports: yes`
- worker task grants `write_task_files: yes` without an explicit coordinator or sub-coordinator reason
- worker report does not confirm `role_boundary_followed: yes`
- worker report claims `coordinator_verdict_given: yes` or `permission_scope_expanded: yes`
- status boards contain invalid lifecycle states or omit assigned agent/report path/next action
- worktree locks omit owner agent, locked file area, workspace mode, or lock status
- event logs contain invalid JSON, missing event fields, invalid event types, or invalid lifecycle statuses
- report says it changed files while task had `modify_source: false`
- report says commit/push/destructive command happened without approval
- report has `prompt_injection_suspected: true` and no coordinator investigation is recorded
- report has only `self_claim` evidence for a high-risk task

## Implementation Note

A minimal validation layer is provided via `scripts/validate-agent-inbox.py` to ensure schema structure and prevent dangerous typos. It is not a complete YAML parser, but strict enough to enforce the protocol.

**Note:** `schema` is the canonical field for the document type, though `schema_type` is supported as an alias for backwards compatibility. Do not specify both with different values.
