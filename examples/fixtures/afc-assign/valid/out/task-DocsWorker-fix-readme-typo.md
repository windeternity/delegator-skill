---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: fix-readme-typo
trace_id: fix-readme-typo
agent_name: DocsWorker
role: implementer
protocol_mode: task-only
coordinator_authority: no
routing_decision: FULL
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
  path: /projects/my-app
  may_create_worktree: no
completion_marker: Completed task: #1
validation_tier: targeted-test
report_path: /projects/my-app/.agent-inbox/report-DocsWorker-fix-readme-typo.md
report_tool: scripts/afc-report.py
created_at: 2026-06-08
---
# Task - DocsWorker fix-readme-typo

## Role Boundary
Worker only: no reassign, scope expansion, or final verdict. Put follow-up in the report.

## Model / Tool / Capability Hint
- preferred: fast-editing model
- reason: Simple text replacement
- fallback: any available model

## Purpose
Fix a typo in the README badge URL.

## Non-Goals
- Do not rewrite the README.
- Do not add new badges.

## Read First
1. README.md

## Acceptance Criteria
- Badge URL points to the correct CI pipeline.
- README renders correctly.

## Evidence To Report
Diff of the changed line.

## Finish
- Check `git diff --name-only`; only locked paths.
- Report: `python -B <report_tool> --task <this_task> --verdict GO --changed-file <p> --evidence-ref x --validation-result pass --summary x --replace`.
