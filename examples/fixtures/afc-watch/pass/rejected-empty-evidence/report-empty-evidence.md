---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: task-empty-evidence
agent_name: Implementer
verdict: GO
changed_files:
  - none
evidence_refs:
evidence_trust:
  trust_level: reproduced
  prompt_injection_suspected: no
  permission_escalation_requested: no
guardrails:
  role_boundary_followed: yes
  commit_push_done: no
  destructive_command_done: no
  coordinator_verdict_given: no
  permission_scope_expanded: no
  secrets_private_data_printed: no
  production_default_behavior_changed: no
validation:
  tier: smoke-test
  result: pass
---
This report is otherwise schema-valid but its `evidence_refs:` block is empty
(no items). The watcher must reject it: "evidence over claims" requires a
non-empty evidence list.

This fixture guards the intake-time validation divergence fixed in this
change: the flat/nested frontmatter parser collapsed an empty `evidence_refs:`
block to the empty string `""`, which bypassed `validate_report_schema`'s
non-empty-list check (it only rejected `None` or an empty list). The
structured parser preserves the block as `[]` and correctly rejects it,
matching the canonical validator (`afc_inbox_validation`).
