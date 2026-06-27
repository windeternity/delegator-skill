---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-closed-poll
agent_name: Worker1
role: implementer
protocol_mode: task-only
coordinator_authority: no
status: CLOSED_GO
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: yes
  run_commands: tests_only
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: existing_edit_worktree
  path: <PROJECT_ROOT>
  may_create_worktree: no
validation_tier: targeted-test
report_path: <PROJECT_ROOT>/.agent-inbox/report-Worker1-closed.md
created_at: 2026-06-08
---
# Task - Closed Poll Demo

## Agent
Worker1

## Role Boundary
You are the assigned worker, not the coordinator.
