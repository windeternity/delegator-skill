# Two-Agent Demo

This example shows the intended pattern without assuming any personal agent names.

## Scenario

A Codex-first coordinator wants two worker agents to help with a small change:

- `Reviewer` performs a read-only guardrail review as a task-only worker.
- `Implementer` performs a bounded edit in a known worktree using a worker brief.

The names are examples only. A real project should define its own roster.
Workers do not receive coordinator authority and must stay inside their task files.

## Files

- `AGENT_ROSTER.md` - example roster with `Role`, `Protocol Mode`, and `Coordinator Authority`
- `STATUS.md` - example task status board with coordinator-owned next actions
- `WORKTREE_LOCKS.md` - example worktree and file-area lock table
- `events.jsonl` - append-only coordination event log example
- `task-Reviewer-guardrail-audit.md` - read-only task file with YAML frontmatter and `Role Boundary`
- `task-Implementer-small-fix.md` - bounded edit task file with YAML frontmatter and `Role Boundary`

## User copy-paste instructions

After copying the task files into the project `.agent-inbox/` directory, give each worker one short instruction:

```text
Read .agent-inbox/task-Reviewer-guardrail-audit.md. Confirm you are Reviewer. Execute only this task within its Permission Scope and write your report to the specified Report Path. Do not modify files, commit, or push.
```

```text
Read .agent-inbox/task-Implementer-small-fix.md. Confirm you are Implementer. Execute only this task within its Permission Scope and write your report to the specified Report Path. Do not commit or push.
```
