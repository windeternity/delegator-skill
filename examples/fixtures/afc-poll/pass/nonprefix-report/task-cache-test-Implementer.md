---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: cache-test
agent_name: Implementer
role: implementer
protocol_mode: task-only
coordinator_authority: no
status: ASSIGNED
permission_scope:
  read_files: yes
  write_reports: yes
  write_task_files: no
  modify_source: yes
  run_commands: tests_only
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: existing_edit_worktree
  path: /tmp/cache-test-wt
  may_create_worktree: no
validation_tier: targeted-test
report_path: <PROJECT_ROOT>/.agent-inbox/cache-test-Implementer.md
created_at: 2026-06-09
---

# Task - Implementer Cache Test

## Purpose
Fixture task for testing schema-based report detection in afc-poll.py.
