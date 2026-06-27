---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-ooo-1
agent_name: WorkerOOO1
role: implementer
protocol_mode: task-only
coordinator_authority: no
status: ASSIGNED
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
  path: /tmp/ooo-1
  may_create_worktree: no
validation_tier: targeted-test
report_path: .agent-inbox/report-WorkerOOO1-task-ooo-1.md
created_at: 2026-06-12
---

# Task - WorkerOOO1

## Agent
WorkerOOO1

## Role Boundary
You are the assigned worker agent for this task, not the coordinator.

## Purpose
Out-of-order fixture task 1.
