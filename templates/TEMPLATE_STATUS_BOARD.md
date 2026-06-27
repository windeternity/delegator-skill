---
schema: agent-file-coordination/status-board
schema_version: 0.1.0
updated_at: <YYYY-MM-DD>
---

# Status Board

<!-- HYDRATION: Replace all <PLACEHOLDER> values with your project-local data. -->

| task_id | assigned_agent | role | protocol_mode | status | dispatched | workspace | report_path | next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <TASK_ID> | <AGENT_NAME> | <ROLE> | <PROTOCOL_MODE> | <STATUS> | <YES_NO> | <WORKSPACE_PATH> | <REPORT_PATH> | <NEXT_ACTION> |

<!-- Status values: DRAFT / ASSIGNED / RUNNING / REPORTED / REVIEWING / NEEDS_FIX / CLOSED_GO / CLOSED_PARTIAL / CLOSED_RED / BLOCKED / CANCELLED / SUPERSEDED
  Dispatched values: yes / no (whether handoff was delivered to worker)
  Next action values (coordinator-owned): wait_for_report / coordinator_review / needs_fix_task / close_task / blocked / assign_worker -->
