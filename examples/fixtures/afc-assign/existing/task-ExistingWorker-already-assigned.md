---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: already-assigned
agent_name: ExistingWorker
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
  path: /projects/existing
  may_create_worktree: no
validation_tier: targeted-test
report_path: /projects/existing/.agent-inbox/report.md
created_at: 2026-06-08
---

# Task - ExistingWorker already-assigned

## Role Boundary
Worker only: no reassign, scope expansion, or final verdict. Put follow-up in the report.

## Purpose
Pre-existing task file for overwrite test.

## Non-Goals
- (none)

## Read First
1. (none)

## Acceptance Criteria
- (test fixture)

## Evidence To Report
(test fixture)

## Finish
- Check `git diff --name-only`; only locked paths.
- Report: `python -B <report_tool> --task <this_task> --verdict GO --changed-file <p> --evidence-ref x --validation-result pass --summary x --replace`.
