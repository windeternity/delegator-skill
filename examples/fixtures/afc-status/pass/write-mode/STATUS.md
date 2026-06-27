---
schema: agent-file-coordination/status-board
schema_version: 0.1.0
updated_at: 2026-06-08
---

# Status Board

| task_id | assigned_agent | role | protocol_mode | status | workspace | report_path | next_action |
| --- | --- | --- | --- | --- | --- | --- | --- |
| task-alpha | Implementer | implementer | task-only | ASSIGNED | <PROJECT_ROOT> | <PROJECT_ROOT>/.agent-inbox/report-Implementer.md | wait_for_report |
| task-beta | Reviewer | reviewer | task-only | REPORTED | <PROJECT_ROOT> | <PROJECT_ROOT>/.agent-inbox/report-Reviewer.md | coordinator_review |
