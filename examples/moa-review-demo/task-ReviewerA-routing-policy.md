---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: moa-routing-review-a
agent_name: ReviewerA
role: reviewer
protocol_mode: task-only
coordinator_authority: no
routing_decision: FULL
coordination_mode: moa_review
comparison_group: moa-routing-policy-001
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
report_path: report-ReviewerA-routing-policy.md
created_at: 2026-06-25
moa:
  layer: candidate
  decision_surface: routing policy MOA gate
  previous_outputs_visible: no
  synthesis_expected: yes
source_artifacts:
  - references/delegation-routing-v1.md
  - docs/WHEN_TO_USE_AFC.md
---
# Task - ReviewerA routing policy review

## Role Boundary

You are the assigned reviewer worker for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.

## Purpose

Review whether the routing policy clearly separates ordinary delegation from MOA review.

## Non-Goals

- Do not edit source files.
- Do not inspect other candidate reports.

## Read First

1. references/delegation-routing-v1.md
2. docs/WHEN_TO_USE_AFC.md

## Acceptance Criteria

- Identify one strength or gap in the MOA routing boundary.
- Cite the source artifact used.
- Confirm no source files changed.
