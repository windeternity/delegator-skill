---
schema: agent-file-coordination/report
schema_version: 0.1.0
agent_name: WorkerBad
verdict: GO
---

# Malformed Report (missing task_id)

This report is missing the required task_id field.
The watcher should reject it (fail-closed) and not wake.
But it should NOT block the valid report from being consumed.
