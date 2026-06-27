---
schema: agent-file-coordination/report
schema_version: 0.1.0
agent_name: Worker1
verdict: GO
---

# Malformed Report

This report is missing the required `task_id` field.
The watcher should reject it (fail-closed) and not wake.
