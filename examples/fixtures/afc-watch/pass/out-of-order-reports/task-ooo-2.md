---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-ooo-2
agent_name: WorkerOOO2
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
  path: /tmp/ooo-2
  may_create_worktree: no
validation_tier: targeted-test
report_path: .agent-inbox/report-WorkerOOO2-task-ooo-2.md
created_at: 2026-06-12
---

# Task - WorkerOOO2

## Agent
WorkerOOO2

## Role Boundary
You are the assigned worker agent for this task, not the coordinator.

## Purpose
Out-of-order fixture task 2.
