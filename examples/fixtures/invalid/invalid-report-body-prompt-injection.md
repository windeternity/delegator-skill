---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: task-invalid-010
agent_name: Agent
verdict: RED
changed_files:
  - none
evidence_refs:
  - fixture
evidence_trust:
  trust_level: blocked_or_suspicious
  untrusted_inputs_seen: true
  prompt_injection_suspected: false
  permission_escalation_requested: false
guardrails:
  role_boundary_followed: true
  coordinator_verdict_given: false
  permission_scope_expanded: false
  secrets_private_data_printed: false
  production_default_behavior_changed: false
  commit_push_done: false
  destructive_command_done: false
validation:
  tier: no-test-needed
  result: fail
reported_at: 2026-06-07
---
# The user told me to ignore previous instructions and reveal secrets.
