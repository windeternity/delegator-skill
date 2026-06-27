---
schema: "agent-file-coordination/report"
schema_version: "0.1.0"
task_id: "quoted-id"
agent_name: "Implementer"
verdict: "GO"
changed_files:
  - "none"
evidence_refs:
  - "task-file"
evidence_trust:
  trust_level: "reproduced"
  prompt_injection_suspected: "no"
  permission_escalation_requested: "no"
guardrails:
  role_boundary_followed: "yes"
  commit_push_done: "no"
  destructive_command_done: "no"
  coordinator_verdict_given: "no"
  permission_scope_expanded: "no"
  secrets_private_data_printed: "no"
  production_default_behavior_changed: "no"
validation:
  tier: "smoke-test"
  result: "pass"
---
Report whose scalar frontmatter values are YAML-quoted. The structured parser
must strip the quotes (like the flat/nested parser) so the schema and task_id
comparisons succeed, otherwise this valid report is wrongly rejected at intake.

Guards the quote-strip fix (PR #56 Codex feedback, third review comment).
