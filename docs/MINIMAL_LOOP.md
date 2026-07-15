# 05 Minimal Coordinator-Worker Loop

This document defines the minimal file-based coordination loop: Coordinator writes task, Worker executes and reports, Validator checks, Coordinator decides next action.

## One-minute Quick Start

Run the complete minimal loop against the demo files:

```powershell
# 1. Validate the demo files (already work)
python -B scripts/validate-agent-inbox.py examples/minimal-loop-demo

# 2. Look at the task
cat examples/minimal-loop-demo/task-Worker-fix-typo.md

# 3. Look at the report
cat examples/minimal-loop-demo/report-Worker-fix-typo.md

# 4. Look at the verdict
cat examples/minimal-loop-demo/verdict-loop-demo-fix-typo.md
```

**Result:** Five steps, four files, zero chat relay.

## Common Scenarios

| User Intent | Starting Point |
| --- | --- |
| "I want to review code before merging" | Read-only reviewer task with `run_commands: tests_only` |
| "I want a second pair of eyes on this design" | MOA review with 2-3 independent workers |
| "This is boring, I don't want to type it" | Implementer task with `modify_source: yes` |
| "I don't know, let me check" | Run `scripts/afc-route.py` first |
| "This is tiny, I'll just do it" | Stay DIRECT — no coordination overhead |

## Loop Definition

```
Step 1: Coordinator → task file
Step 2: Worker → executes within permission scope
Step 3: Worker → report file
Step 4: Validator → checks task + report
Step 5: Coordinator → verdict + next action
```

Five steps, four files, zero chat relay.

## File Naming

| Step | File Pattern | Owner |
| --- | --- | --- |
| Task | `.agent-inbox/task-<Agent Name>-<short-id>.md` | Coordinator |
| Report | `.agent-inbox/report-<Agent Name>-<short-id>.md` | Worker |
| Verdict | `.agent-inbox/verdict-<short-id>.md` | Coordinator |

## Step 1: Coordinator Writes Task

The task file must include:

- YAML frontmatter with `schema: agent-file-coordination/task`
- `task_id`, `agent_name`, `role`, `protocol_mode`
- `permission_scope` with explicit `run_commands` level
- `workspace` with `mode` and `path`
- `validation_tier` and `report_path`
- `## Role Boundary` section in the body

The coordinator must not embed executable instructions that contradict the permission scope.

## Step 2: Worker Executes

The worker:

1. Reads the task file.
2. Confirms its identity matches `agent_name`.
3. Executes within the declared `permission_scope`.
4. Does not create tasks, reassign work, or approve final verdicts.

## Step 3: Worker Writes Report

The report file must include:

- YAML frontmatter with `schema: agent-file-coordination/report`
- Matching `task_id` and `agent_name`
- `verdict` field: `GO`, `PARTIAL`, or `RED`
- `changed_files` list (or `none`)
- `evidence_refs` list (non-empty)
- `evidence_trust` block
- `guardrails` block with all keys confirmed
- `validation` block with `tier` and `result`

The report body should include:

- `## Summary` — what was done
- Evidence of changes or findings
- Remaining risk (if any)

## Step 4: Validator Checks

Run:

```powershell
python -B scripts/validate-agent-inbox.py <inbox-directory>
```

The validator checks:

- Frontmatter schema compliance
- `task_id` and `agent_name` consistency between task and report
- `verdict` is a valid value
- `evidence_refs` is non-empty
- `guardrails` block is complete
- `coordination_mode` consistency
- No dangerous phrases or permission escalation

## Step 5: Coordinator Decides

The coordinator reads the report and validator output, then writes a verdict:

- **GO** — task complete, close or proceed to next task
- **PARTIAL** — partial progress, create follow-up task
- **RED** — blocked or failed, escalate or abort

The verdict file uses `schema: agent-file-coordination/coordinator-verdict`.

## Permission Levels for Loop Tasks

| Task Intent | `run_commands` |
| --- | --- |
| Read-only review | `none` or `read_only` |
| Run tests only | `tests_only` |
| Branch create/switch | `bounded` |
| Edit + test | `tests_only` (if tests cover the edit) |

See `references/action-permission-matrix.md` for the full matrix.

## Example

See `examples/minimal-loop-demo/` for a complete end-to-end example:

1. `task-Worker-fix-typo.md` — coordinator task
2. `sample.py` — target file
3. `report-Worker-fix-typo.md` — worker report
4. `verdict-loop-demo-fix-typo.md` — coordinator verdict

## Validation

```powershell
# Validate demo files
python -B scripts/validate-agent-inbox.py examples/minimal-loop-demo

# Run loop fixture tests
python -B examples/fixtures/afc-loop/run-tests.py

# Run all shared tests
python -B examples/fixtures/afc-shared/run-tests.py
```
