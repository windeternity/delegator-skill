---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: artifact-test
agent_name: Worker
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
  path: /tmp/artifact-test
  may_create_worktree: no
validation_tier: targeted-test
report_path: /tmp/artifact-test-report.md
created_at: 2026-06-12
---

# Task with artifacts directory

## Role Boundary
You are the assigned worker agent for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.
