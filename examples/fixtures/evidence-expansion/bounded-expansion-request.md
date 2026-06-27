---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: h3-fixture-bounded-request
agent_name: Coordinator
role: coordinator
protocol_mode: full-skill
coordinator_authority: yes
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: no
  run_commands: none
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: read_only_shared
  path: .
  may_create_worktree: no
validation_tier: no-test-needed
report_path: .agent-inbox/report-Coordinator.md
created_at: 2026-06-11
---

# Fixture — Bounded Expansion Request (coordinator-authored)

## Role Boundary

You are the coordinator. You are authorized to issue this Evidence Expansion Request and to give final GO/PARTIAL/RED verdicts. You may not create new tasks because `write_task_files: no`.

## Evidence Expansion Request

```yaml
task_id: h3-fixture-bounded-request
artifact_id: artifact-lint-001
reason: Need actual/expected diff around line 42 to write a precise fix instruction.
requested_window:
  form: line_range
  start_line: 40
  end_line: 50
max_bytes: 4096
max_tokens: 1024
request_number: 1
request_limit: 3
```

## Notes

- `artifact_id: artifact-lint-001` is already referenced by H2 Compact Probe Evidence for this task.
- `requested_window` uses the structured `line_range` form, not a free-form command.
- `max_bytes` (4096) and `max_tokens` (1024) are within hard maximums.
- `request_number: 1` is within `request_limit: 3`.
- This request is coordinator-authored; workers may recommend but cannot authorize.
