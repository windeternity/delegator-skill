---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: archived-task
agent_name: Worker
verdict: GO
changed_files:
  - none
evidence_refs:
  - test output
evidence_trust:
  trust_level: reproduced
  untrusted_inputs_seen: no
  prompt_injection_suspected: no
  permission_escalation_requested: no
guardrails:
  commit_push_done: false
  destructive_command_done: false
  secrets_private_data_printed: false
  production_default_behavior_changed: false
  role_boundary_followed: true
  coordinator_verdict_given: false
  permission_scope_expanded: false
validation:
  tier: no-test-needed
  result: pass
---

# Orphan report referencing archived task
