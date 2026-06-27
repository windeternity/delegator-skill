---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: task-valid-release-operator-001
agent_name: ReleaseBot
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
  commit_push: approved
  destructive_actions: no
workspace:
  mode: existing_edit_worktree
  path: .
  may_create_worktree: no
  branch: codex/release-changelog
  locked_files_or_areas: CHANGELOG.md, VERSION
validation_tier: targeted-test
report_path: .agent-inbox/report-ReleaseBot.md
created_at: 2026-06-12
---
# Task - ReleaseBot Release Changelog Update

## Agent
ReleaseBot

## Role
implementer

## Protocol Mode
task-only

## Coordinator Authority
no

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
- `commit_push`: approved
- `destructive_actions`: no

## Workspace Mode
- `mode`: existing_edit_worktree
- `path`: .
- `may_create_worktree`: no

## Release Operations Scope
- Target branch: codex/release-changelog
- Allowed operations: commit, push, open PR
- Staged-file allowlist: CHANGELOG.md, VERSION

## Purpose
Update CHANGELOG.md and VERSION for the upcoming release.

## Non-Goals
- Do not modify source code.
- Do not merge PRs.

## Acceptance Criteria
- CHANGELOG.md reflects the correct version and date.
- VERSION file updated.
- Staged-file allowlist enforced.

## Report Path
.agent-inbox/report-ReleaseBot.md
