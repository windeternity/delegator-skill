# Protocol Spec v0.1 — Task Bundle and Context Manifest

This document is an **extension note** for the `agent-file-coordination` protocol. It does not replace `references/task-report-schema.md` or change existing schema identifiers. All fields defined here are **optional**; task files without them remain fully valid.

## Purpose

A Task Bundle turns a task file from "instruction plus permissions" into a compact **coordinator-owned authorization source** for a single task. The coordinator provides minimal context slices, not full-repository prompt stuffing.

## Optional Task Bundle fields

These fields may appear in task YAML frontmatter or in a companion context manifest. They are additive only.

| Field | Type | Description |
|---|---|---|
| `objective` | string | One-line task objective. Replaces or shortens the free-form title. |
| `non_objectives` | list of strings | Explicitly out-of-scope items. |
| `risk_level` | string | One of `standard`, `sensitive`, `critical`. Default is `standard`. |
| `modifiable_targets` | list of strings | Files, directories, or symbol patterns the worker may edit. Must be empty or omitted when `permission_scope.modify_source` is `no`. |
| `read_only_references` | list of strings | Files or symbols the worker may read but must not modify. |
| `forbidden_zones` | list of strings | Files, directories, or topics the worker must not touch. |
| `validation_profiles` | list of strings | Opaque validation profile identifiers (e.g., `lint`, `typecheck`, `unit_targeted`). The coordinator or a trusted script maps these to concrete commands; workers must not pass executable command strings. |
| `artifact_policy` | string | One of `inline`, `attach`, `omit`. Default is `inline` for small evidence, `attach` for logs or screenshots. |
| `report_path` | string | Already defined in base schema; in a Task Bundle it is the single authorized report destination. |

## Risk levels

- `standard` — minimal interruption; worker proceeds unless evidence is suspicious.
- `sensitive` — stops for permission escalation, repeated failure, scope change, or suspicious evidence.
- `critical` — requires human approval before execution, before merge-like actions, and before final closure when independent evidence is unavailable.

## Validation profile identifiers

Validation profiles are **coordinator-selected opaque labels** that enumerate the required or allowed validation checks for a task. The coordinator decides which profiles apply; the worker must not choose, expand, or override them. A trusted script, probe, or external adapter maps the label to the actual command. This prevents workers from passing executable strings through reports.

Workers may later submit a declarative Validation Request (H2) within the coordinator-authorized bounds, but the profile list itself remains coordinator-owned.

Example identifiers (generic; H2 will define the catalog):

- `lint` — static analysis / linting
- `typecheck` — type-system check
- `unit_targeted` — unit tests for changed files
- `unit_changed` — unit tests selected by diff
- `build_smoke` — minimal build verification

Workers must not include shell command strings in `validation_profiles` or in report fields.

## Context manifest companion (optional)

For tasks that need more than ~4 KB of context, the coordinator may provide a separate context manifest file instead of inflating the task body. The manifest is a plain Markdown or YAML file referenced by the canonical task file; it does not introduce a new schema identifier. It may contain the Task Bundle fields above in frontmatter or body sections.

Rules:
- The task file remains the authoritative permission source.
- The manifest may be referenced by `context_manifest_path` in the task frontmatter.
- If the manifest conflicts with the task file, the task file wins.

## Backward compatibility

- Existing `agent-file-coordination/*` schema identifiers remain unchanged.
- `schema_version: 0.1.0` remains valid.
- Unknown frontmatter keys are ignored by `validate-agent-inbox.py`.
- Task files without any Task Bundle fields are still fully valid.

## Example: minimal Task Bundle

```yaml
---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: h1-example-minimal
agent_name: DocsWorker
role: docs
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
  path: .
  may_create_worktree: no
validation_tier: no-test-needed
report_path: .agent-inbox/report-DocsWorker.md
created_at: 2026-06-11
objective: Update the protocol spec extension note
non_objectives:
  - Do not change the base schema
  - Do not add mandatory runtime behavior
risk_level: standard
modifiable_targets: []
read_only_references:
  - references/task-report-schema.md
forbidden_zones:
  - SKILL.md
  - scripts/
validation_profiles:
  - lint
artifact_policy: inline
---
```

## Example: legacy task without Task Bundle fields

A task file that omits all Task Bundle fields is still valid and processed exactly as before.

```yaml
---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: h1-example-legacy
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
  path: .
  may_create_worktree: no
validation_tier: no-test-needed
report_path: .agent-inbox/report-Reviewer.md
created_at: 2026-06-11
---
```

## Non-goals

- This spec does not define the Validation Catalog (H2).
- This spec does not define Compact Probe Evidence (H2).
- This spec does not define Evidence Expansion (H3).
- This spec does not define differential validation taxonomy (H4).
- This spec does not add mandatory runtime behavior or executable command strings.
