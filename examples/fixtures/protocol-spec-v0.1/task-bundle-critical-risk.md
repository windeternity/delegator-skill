---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: h1-fixture-critical-risk
agent_name: Smoke
role: smoke
protocol_mode: task-only
coordinator_authority: no
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: no
  run_commands: tests_only
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: existing_edit_worktree
  path: .
  may_create_worktree: no
validation_tier: targeted-test
report_path: .agent-inbox/report-Smoke.md
created_at: 2026-06-11
objective: Run targeted smoke tests on the build
non_objectives: ["Do not run the full suite", "Do not modify source"]
risk_level: critical
modifiable_targets: []
read_only_references: ["scripts/"]
forbidden_zones: [".agent-inbox/"]
validation_profiles: ["build_smoke", "unit_targeted"]
artifact_policy: attach
---

# Task - Smoke critical-risk fixture

## Role Boundary
You are the assigned worker agent for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.

## Permission Scope
- `read_files`: yes
- `write_task_files`: no
- `write_reports`: yes
- `modify_source`: no
- `run_commands`: tests_only
- `network_access`: none
- `commit_push`: no
- `destructive_actions`: no
