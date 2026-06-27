---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: poll-c
agent_name: Worker3
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
report_path: <PROJECT_ROOT>/.agent-inbox/report-Worker3.md
created_at: 2026-06-09
---
# Task - Poll C

## Agent
Worker3

## Role Boundary
You are the assigned worker, not the coordinator.
