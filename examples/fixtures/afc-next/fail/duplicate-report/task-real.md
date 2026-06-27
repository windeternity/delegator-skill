---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-real
agent_name: Worker1
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
  mode: read_only_shared
  path: <PROJECT_ROOT>
  may_create_worktree: no
validation_tier: no-test-needed
report_path: <PROJECT_ROOT>/.agent-inbox/report-Worker1-next-dupr.md
created_at: 2026-06-11
---
# Task - Dup Report

## Role Boundary
You are the assigned worker, not the coordinator.
