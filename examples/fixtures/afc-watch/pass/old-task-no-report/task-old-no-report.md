---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-old-no-report
agent_name: Worker4
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
  path: /tmp/old-test
  may_create_worktree: no
validation_tier: targeted-test
report_path: .agent-inbox/report-Worker4-old.md
created_at: 2026-01-01
---

# Task - Worker4 Old No Report

## Agent
Worker4

## Role Boundary
You are the assigned worker agent for this task, not the coordinator.

## Purpose
Genuinely old ASSIGNED task for afc-watch.py staleness alarm regression test.
This task has a date-only created_at (2026-01-01) and its file mtime is
explicitly set to an old timestamp, so it should trigger stale_alarm with
a modest threshold (e.g. 3600 seconds).
