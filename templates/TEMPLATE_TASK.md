---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: <TASK_ID>
agent_name: <AGENT_NAME>
role: <ROLE>
protocol_mode: <PROTOCOL_MODE>
coordinator_authority: <COORDINATOR_AUTHORITY>
routing_decision: FULL
coordination_mode: <OPTIONAL_COORDINATION_MODE>
comparison_group: <OPTIONAL_COMPARISON_GROUP>
status: DRAFT
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: <YES_OR_NO>
  run_commands: <COMMAND_LEVEL>
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: <WORKSPACE_MODE>
  path: <WORKSPACE_PATH>
  may_create_worktree: <YES_OR_NO_OR_ASK>
  branch: <BRANCH_NAME>
  base: <BASE_REVISION>
  locked_files_or_areas: <FILE_OR_DIR_LIST>
validation_tier: <VALIDATION_TIER>
validation_command: <OPTIONAL_SINGLE_LINE_CODE_GATE_COMMAND>
report_path: <REPORT_PATH>
report_tool: <ABSOLUTE_AFC_REPORT_TOOL_PATH>
completion_marker: <OPTIONAL_EXPECTED_FINAL_CHAT_MARKER>
created_at: <YYYY-MM-DD>
source_artifacts: <OPTIONAL_SOURCE_ARTIFACT_PATHS>
moa:
  layer: <OPTIONAL_CANDIDATE_OR_SYNTHESIS>
  decision_surface: <OPTIONAL_DECISION_SURFACE>
---
# Task - <TASK_TITLE>

## Role Boundary

Worker only: no reassign, scope expansion, or final verdict. Put follow-up in the report.

## Purpose

<TASK_PURPOSE>

## Non-Goals

- <NONE_OR_OUT_OF_SCOPE>

## Read First

1. <FILE_OR_POINTER>

## Acceptance Criteria

- <CRITERION_1>

## Shared Rules (referenced, not repeated)

- Frontmatter permission scope and `locked_files_or_areas` are authoritative.
- Follow `references/worker-brief.md`; do not restate generic conduct rules.
- For MOA tasks, follow `references/moa-coordination-modes.md` and `references/moa-synthesis-rubric.md`.
- For protocol/schema contracts, apply `references/protocol-design-review-checklist.md`.

## Evidence To Report

Use `scripts/afc-report.py`; give changed paths and short command or artifact
refs, not logs or diffs.

## Finish

- Budget: stay under 4 KiB; move context to referenced files.
- Check `git diff --name-only`; only locked paths.
- Report: `python -B <report_tool> --task <this_task> --verdict GO --changed-file <p> --evidence-ref x --validation-result pass --summary x --replace`
