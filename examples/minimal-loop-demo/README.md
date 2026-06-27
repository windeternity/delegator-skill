# Minimal Loop Demo

This example demonstrates the minimal Coordinator → Worker → Report → Validate → Next Action loop using local files.

## Loop Steps

```
1. Coordinator writes task      → task-Worker-fix-typo.md
2. Worker executes               → fixes typo in sample.py
3. Worker writes report          → report-Worker-fix-typo.md
4. Validator checks task+report  → python -B scripts/validate-agent-inbox.py examples/minimal-loop-demo
5. Coordinator reads report      → verdict-loop-demo-fix-typo.md (GO, close)
```

## Files

| File | Owner | Step |
| --- | --- | --- |
| `task-Worker-fix-typo.md` | Coordinator | 1. Task definition |
| `sample.py` | Repository | Target file with typo |
| `report-Worker-fix-typo.md` | Worker | 3. Structured report |
| `verdict-loop-demo-fix-typo.md` | Coordinator | 5. Final verdict + next action |

## How to Validate

```powershell
# Validate task + report pair
python -B scripts/validate-agent-inbox.py examples/minimal-loop-demo

# Run shared fixture tests (includes loop fixtures)
python -B examples/fixtures/afc-shared/run-tests.py
```

## Key Properties

- **File-based**: All coordination happens through files, not chat messages.
- **Inspectable**: Every step produces a file that can be reviewed.
- **Permission-bounded**: Worker stays inside its task permission scope.
- **Deterministic**: Validator checks schema, guardrails, and evidence refs.
- **No orchestration platform**: No MCP, no queue, no DAG engine — just files.
