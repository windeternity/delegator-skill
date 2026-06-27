---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-fresh
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
  mode: existing_edit_worktree
  path: /tmp/fresh-test
  may_create_worktree: no
validation_tier: targeted-test
report_path: .agent-inbox/report-Worker3-fresh.md
created_at: 2026-06-12
---

# Task - Worker3 Fresh Test

## Agent
Worker3

## Role Boundary
You are the assigned worker agent for this task, not the coordinator.

## Purpose
Fresh task for afc-watch.py staleness precision regression test.
This task has a date-only created_at (2026-06-12) which would be
interpreted as 2026-06-12T00:00:00Z by datetime.fromisoformat(),
making it appear hundreds of minutes old. The fix uses the task
file's mtime as the age source for date-only created_at, so this
freshly created task should NOT trigger stale_alarm with a
multi-hour threshold.
