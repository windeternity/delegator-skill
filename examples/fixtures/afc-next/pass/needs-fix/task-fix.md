---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-fix
agent_name: Worker4
role: implementer
protocol_mode: task-only
coordinator_authority: no
status: NEEDS_FIX
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: yes
  run_commands: bounded
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: existing_edit_worktree
  path: <PROJECT_ROOT>
  may_create_worktree: no
validation_tier: targeted-test
report_path: <PROJECT_ROOT>/.agent-inbox/report-Worker4-next-e.md
created_at: 2026-06-11
---
# Task - Needs Fix Case

## Role Boundary
You are the assigned worker, not the coordinator.
