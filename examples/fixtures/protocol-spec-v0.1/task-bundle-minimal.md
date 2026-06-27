---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: h1-fixture-bundle-minimal
agent_name: Reviewer
role: reviewer
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
  path: .
  may_create_worktree: no
validation_tier: no-test-needed
report_path: .agent-inbox/report-Reviewer.md
created_at: 2026-06-11
---

# Task - Reviewer minimal fixture

## Role Boundary
You are the assigned reviewer worker for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.

## Permission Scope
- `read_files`: yes
- `write_task_files`: no
- `write_reports`: yes
- `modify_source`: no
- `run_commands`: none
- `network_access`: none
- `commit_push`: no
- `destructive_actions`: no
