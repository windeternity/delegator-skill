---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: h2-fixture-allowed-request
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
  mode: existing_edit_worktree
  path: .
  may_create_worktree: no
validation_tier: targeted-test
report_path: .agent-inbox/report-Implementer.md
created_at: 2026-06-11
objective: Add a new helper function
non_objectives: ["Do not change public API", "Do not add dependencies"]
risk_level: standard
modifiable_targets: ["src/helpers.py"]
read_only_references: ["tests/test_helpers.py"]
forbidden_zones: ["docs/", "scripts/"]
validation_profiles: ["lint", "unit_targeted"]
artifact_policy: inline
---

# Task - Implementer allowed validation request

## Role Boundary
You are the assigned worker agent for this task, not the coordinator.
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

## Validation Request

The worker submits this request within the authorized profile list:

```yaml
profile: lint
selector: src/helpers.py
reason: Changed src/helpers.py may have style violations.
```

This request is allowed because `lint` is in the Task Bundle `validation_profiles: [lint, unit_targeted]`.
