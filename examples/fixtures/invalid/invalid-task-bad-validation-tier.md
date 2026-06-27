---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-invalid-004
agent_name: Implementer
role: implementer
protocol_mode: task-only
coordinator_authority: no
status: ASSIGNED
permission_scope:
  read_files: true
  write_task_files: no
  write_reports: yes
  modify_source: false
  run_commands: none
  network_access: none
  commit_push: no
  destructive_actions: false
workspace:
  mode: read_only_shared
  path: .
  may_create_worktree: no
validation_tier: just-trust-me
report_path: .agent-inbox/report-Implementer.md
created_at: 2026-06-07
---
# Task with bad tier

## Role Boundary
You are the assigned worker for this task, not the coordinator.
