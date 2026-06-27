---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: archive-policy-fixture-closed-go
agent_name: Implementer
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
  path: <PROJECT_ROOT>-worktrees/sprint6-c2-fixture
  may_create_worktree: no
validation_tier: targeted-test
report_path: <PROJECT_ROOT>/.agent-inbox/archive-policy-fixture-closed-go-report.md
created_at: 2026-06-10
---
# Task - Implementer Closed CLOSED_GO fixture

## Agent
Implementer

## Role Boundary
You are the assigned implementer worker for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.

## Permission Scope
- `read_files`: yes
- `write_task_files`: no
- `write_reports`: yes
- `modify_source`: yes
- `run_commands`: tests_only
- `network_access`: none
- `commit_push`: no
- `destructive_actions`: no

## Archive Policy Note
`CLOSED_GO` is a terminal state. This fixture demonstrates the
"after-archive" view: the task file in `archive/<YYYY-MM>/` keeps its
original filename and `task_id`, and is referenced from
`.agent-inbox/archive/2026-06/` rather than the active inbox.
