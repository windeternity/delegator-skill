# Template Hydration Demo

This example shows a hydrated project after first-use template setup. All values are generic and public-safe.

## Scenario

A coordinator has hydrated the placeholder templates into a project-local `.agent-inbox/` with:

- One coordinator agent
- One reviewer agent (read-only)
- One implementer agent (bounded edits)

The demo shows the roster, status board, worktree locks, a task file, a report file, a coordinator verdict, and the event log after one complete coordination cycle.

## Hydration Flow

1. Copy `templates/TEMPLATE_ROSTER.md` to `.agent-inbox/AGENT_ROSTER.md` and fill in agent names, tools, models, and capabilities.
2. Copy `templates/TEMPLATE_STATUS_BOARD.md` to `.agent-inbox/STATUS.md`.
3. Copy `templates/TEMPLATE_WORKTREE_LOCKS.md` to `.agent-inbox/WORKTREE_LOCKS.md`.
4. Create `.agent-inbox/events.jsonl` with an initial `ROSTER_UPDATED` event.
5. For each task, copy `templates/TEMPLATE_TASK.md` and fill in the task-specific placeholders.

## Files

- `AGENT_ROSTER.md` — hydrated roster with generic agent names
- `STATUS.md` — status board after one task cycle
- `WORKTREE_LOCKS.md` — worktree locks for the coordination cycle
- `events.jsonl` — event log from roster creation through task closure
- `task-Reviewer-guardrail-audit.md` — hydrated reviewer task
- `report-Reviewer-guardrail-audit.md` — hydrated reviewer report
- `verdict-Reviewer-guardrail-audit.md` — hydrated coordinator verdict

## Validation

```powershell
python -B scripts\validate-agent-inbox.py examples\template-hydration-demo
```
