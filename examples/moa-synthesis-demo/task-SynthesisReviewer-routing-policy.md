---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: moa-routing-synthesis
agent_name: SynthesisReviewer
role: reviewer
protocol_mode: task-only
coordinator_authority: no
routing_decision: FULL
coordination_mode: moa_synthesis
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
report_path: report-SynthesisReviewer-routing-policy.md
created_at: 2026-06-25
moa:
  layer: synthesis
  decision_surface: routing policy MOA gate
  inputs:
    - examples/moa-review-demo/report-ReviewerA-routing-policy.md
    - examples/moa-review-demo/report-ReviewerB-routing-policy.md
source_artifacts:
  - references/moa-synthesis-rubric.md
---
# Task - SynthesisReviewer routing policy synthesis

## Role Boundary

You are the assigned synthesis reviewer for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.

## Purpose

Compare the candidate MOA review reports and recommend a coordinator decision.

## Non-Goals

- Do not edit source files.
- Do not issue the final coordinator verdict.

## Read First

1. examples/moa-review-demo/report-ReviewerA-routing-policy.md
2. examples/moa-review-demo/report-ReviewerB-routing-policy.md
3. references/moa-synthesis-rubric.md

## Acceptance Criteria

- Compare agreements and contradictions.
- Rank evidence quality.
- Identify validation gaps.
- Recommend GO, PARTIAL, RED, or SPLIT for the coordinator.
