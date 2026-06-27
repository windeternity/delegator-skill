---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-invalid-018
agent_name: Reporter
role: reviewer
protocol_mode: task-only
coordinator_authority: no
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
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
report_path: .agent-inbox/report-Reporter.md
created_at: 2026-06-07
---
# Missing write_reports permission

## Role Boundary
You are the assigned worker for this task, not the coordinator.
