---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: real-task-001
agent_name: Implementer
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
  mode: manual_worktree_needed
  path: <PROJECT_ROOT>-worktrees/fix
  may_create_worktree: no
  branch: task/fix
  locked_files_or_areas: src/
validation_tier: targeted-test
report_path: .agent-inbox/report-Implementer.md
created_at: 2026-06-08
---
# Task - Implementer

## Agent
Implementer

## Role Boundary
You are the assigned implementer worker for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.

## Permission Scope
Bounded edit. Report writing allowed only at the specified report path.
