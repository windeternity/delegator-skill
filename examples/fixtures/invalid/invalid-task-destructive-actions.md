---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-invalid-007
agent_name: BadAgent
role: implementer
protocol_mode: worker-brief
coordinator_authority: no
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: yes
  run_commands: bounded
  network_access: none
  commit_push: no
  destructive_actions: true
workspace:
  mode: existing_edit_worktree
  path: .
  may_create_worktree: no
validation_tier: no-test-needed
report_path: .agent-inbox/report-BadAgent.md
created_at: 2026-06-07
---
# Destructive actions enabled

## Role Boundary
You are the assigned worker for this task, not the coordinator.
