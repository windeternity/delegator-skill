---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: demo-reviewer-guardrail-audit
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
  path: examples/two-agent-demo
  may_create_worktree: no
validation_tier: no-test-needed
report_path: .agent-inbox/report-Reviewer-guardrail-audit.md
created_at: 2026-06-07
---

# Task - Reviewer Guardrail Audit

## Agent
Reviewer

## Role Boundary
You are the assigned reviewer worker for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.

## Model / Tool / Capability Hint
- preferred: high reasoning capability model
- reason: read-only guardrail review
- fallback: any model/tool that can read files and write a structured report
- verification: unknown
- smoke_test_needed: no

## Purpose
Inspect the current plan and codebase to ensure that the proposed small fix does not violate any project guardrails or security policies.

## Non-Goals
- Do not write or modify any code.
- Do not execute scripts or tests.

## Permission Scope
- `read_files`: yes
- `write_task_files`: no
- `write_reports`: yes
- `modify_source`: no
- `run_commands`: none
- `network_access`: none
- `commit_push`: no
- `destructive_actions`: no
- `write_reports` allows writing only the specified Report Path, not task files

## Workspace Mode
- `mode`: read_only_shared
- `path`: examples/two-agent-demo
- `may_create_worktree`: no

## Read First
- `AGENT_ROSTER.md`
- Relevant configuration or security guidelines in the repository.

## Guardrails
- MUST NOT modify any files.
- MUST NOT execute shell commands.
- MUST NOT create new task files or act as coordinator.
- MUST NOT approve final GO/PARTIAL/RED.

## Validation Tier
no-test-needed

## Acceptance Criteria
- A comprehensive audit report is generated.
- The report clearly concludes with a verdict (GO, PARTIAL, or RED).

## Evidence To Report
- List of reviewed files.
- Identified potential risks or violations.
- Recommended adjustments if the verdict is PARTIAL or RED.
- Role-boundary and permission-scope guardrail confirmations.

## Report Path
`.agent-inbox/report-Reviewer-guardrail-audit.md`
