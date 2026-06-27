---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-wait
agent_name: Worker2
role: implementer
protocol_mode: task-only
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
  destructive_actions: no
workspace:
  mode: existing_edit_worktree
  path: <PROJECT_ROOT>
  may_create_worktree: no
validation_tier: targeted-test
report_path: <PROJECT_ROOT>/.agent-inbox/report-Worker2-next-c.md
created_at: 2026-06-11
---
# Task - Wait Case

## Role Boundary
You are the assigned worker, not the coordinator.
