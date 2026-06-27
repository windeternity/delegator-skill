---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-valid-mp
agent_name: WorkerMP
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
  path: /tmp/mp
  may_create_worktree: no
validation_tier: targeted-test
report_path: .agent-inbox/report-WorkerMP-task-valid-mp.md
created_at: 2026-06-12
---

# Task - WorkerMP Valid

## Agent
WorkerMP

## Role Boundary
You are the assigned worker agent for this task, not the coordinator.

## Purpose
Malformed-plus-valid fixture task.
