---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: gamma
agent_name: Reviewer
role: reviewer
protocol_mode: task-only
coordinator_authority: no
status: NEEDS_FIX
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
  path: /tmp/gamma
  may_create_worktree: no
validation_tier: no-test-needed
report_path: /tmp/gamma-report.md
created_at: 2026-06-10
---

# Active task gamma (NEEDS_FIX)

## Role Boundary
You are the assigned worker agent for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.
