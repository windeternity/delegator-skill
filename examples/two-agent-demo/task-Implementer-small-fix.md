---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: demo-implementer-small-fix
agent_name: Implementer
role: implementer
protocol_mode: worker-brief
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
  path: examples/two-agent-demo
  may_create_worktree: no
validation_tier: targeted-test
report_path: .agent-inbox/report-Implementer-small-fix.md
created_at: 2026-06-07
---

# Task - Implementer Small Fix

## Agent
Implementer

## Role Boundary
You are the assigned implementer worker for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.

## Model / Tool / Capability Hint
- preferred: code-capable model
- reason: bounded edit plus targeted local validation
- fallback: any model/tool that can edit files and run tests only
- verification: unknown
- smoke_test_needed: no

## Purpose
Implement the bounded edit as described in the coordination plan.

## Non-Goals
- Do not refactor unrelated components.
- Do not commit or push the changes.

## Permission Scope
- `read_files`: yes
- `write_task_files`: no
- `write_reports`: yes
- `modify_source`: yes
- `run_commands`: tests_only
- `network_access`: none
- `commit_push`: no
- `destructive_actions`: no
- `write_reports` allows writing only the specified Report Path, not task files

## Workspace Mode
- `mode`: existing_edit_worktree
- `path`: examples/two-agent-demo
- `may_create_worktree`: no
- Do not create a branch or worktree unless the coordinator provides one.

## Read First
- `.agent-inbox/report-Reviewer-guardrail-audit.md` (if verdict is GO).
- Source files designated for the fix.

## Guardrails
- MUST NOT change the overall architecture.
- MUST NOT touch files outside the designated scope.
- MUST NOT push code.
- MUST NOT create new task files or act as coordinator.
- MUST NOT approve final GO/PARTIAL/RED.

## Validation Tier
targeted-test

## Acceptance Criteria
- The target files are successfully modified to apply the fix.
- Existing tests pass locally.

## Evidence To Report
- Summary of lines or files changed.
- Local test execution results.
- Role-boundary and permission-scope guardrail confirmations.

## Report Path
`.agent-inbox/report-Implementer-small-fix.md`
