---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: moa-routing-review-b
agent_name: ReviewerB
verdict: PARTIAL
coordination_mode: moa_review
comparison_group: moa-routing-policy-001
changed_files:
  - none
evidence_refs:
  - docs/WHEN_TO_USE_AFC.md
  - references/moa-synthesis-rubric.md
evidence_trust:
  trust_level: referenced
  untrusted_inputs_seen: no
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
  tier: no-test-needed
  result: pass
reported_at: 2026-06-25
---
# Worker Report

The usage guide says not to count votes, but readers may still miss that synthesis needs evidence ranking. The synthesis rubric closes the gap, so the candidate recommendation is to link both documents together.

Remaining risk: none for this read-only fixture.

