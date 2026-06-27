---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: <TASK_ID>
agent_name: <AGENT_NAME>
verdict: <GO_PARTIAL_OR_RED>
coordination_mode: <OPTIONAL_COORDINATION_MODE>
comparison_group: <OPTIONAL_COMPARISON_GROUP>
changed_files:
  - <CHANGED_FILE_OR_NONE>
evidence_refs:
  - <SHORT_COMMAND_OR_ARTIFACT_PATH>
evidence_trust:
  trust_level: referenced
  untrusted_inputs_seen: <YES_OR_NO>
  prompt_injection_suspected: no
  permission_escalation_requested: no
guardrails:
  role_boundary_followed: yes
  coordinator_verdict_given: no
  permission_scope_expanded: no
  secrets_private_data_printed: no
  production_default_behavior_changed: no
  commit_push_done: no
  destructive_command_done: no
validation:
  tier: <VALIDATION_TIER>
  result: <PASS_PARTIAL_FAIL_OR_NOT_RUN>
reported_at: <YYYY-MM-DD>
---

# Worker Report

<SUMMARY_UNDER_600_CHARACTERS>

Remaining risk: <NONE_OR_SHORT_RISK>
