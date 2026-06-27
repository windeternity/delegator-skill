---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-stale
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
  run_commands: tests_only
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: existing_edit_worktree
  path: /tmp/stale-test
  may_create_worktree: no
validation_tier: targeted-test
report_path: .agent-inbox/report-Worker2-stale.md
created_at: 2026-01-01
---

# Task - Worker2 Stale Test

## Agent
Worker2

## Role Boundary
You are the assigned worker agent for this task, not the coordinator.

## Purpose
Stale task for afc-watch.py staleness alarm fixture.
This task was created on 2026-01-01 and has no report.
With a short staleness threshold, the watcher should fire a stale_alarm.
