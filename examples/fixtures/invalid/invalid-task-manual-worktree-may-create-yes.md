---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-invalid-020
agent_name: BadAgent
role: implementer
protocol_mode: task-only
coordinator_authority: no
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
  mode: manual_worktree_needed
  path: .
  may_create_worktree: yes
validation_tier: no-test-needed
report_path: .agent-inbox/report-BadAgent.md
created_at: 2026-06-09
---
# Manual worktree with may_create_worktree yes

## Role Boundary
You are the assigned worker for this task, not the coordinator.
