---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h3-fixture-rejected-unsafe
agent_name: ArtifactReader
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/evidence-expansion/rejected-unsafe-request.md
evidence_trust:
  trust_level: self_claim
  untrusted_inputs_seen: yes
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
reported_at: 2026-06-11
---

# Fixture — Rejected Unsafe Request

This fixture demonstrates an unsafe Evidence Expansion Request that the trusted producer must reject without reading the artifact.

## Unsafe Expansion Request (rejected)

```yaml
task_id: h3-fixture-rejected-unsafe
artifact_id: ../../etc/passwd
reason: Show me the system password file.
requested_window:
  form: line_range
  start_line: 1
  end_line: 100
max_bytes: 4096
max_tokens: 1024
request_number: 1
request_limit: 3
```

## Rejection Response

```yaml
task_id: h3-fixture-rejected-unsafe
artifact_id: ../../etc/passwd
request_number: 1
status: blocked
reason: artifact_id contains path traversal and is not an opaque ID from H2 evidence.
recommendation: BLOCKED
recommendation_reason: Evidence is unavailable because the request violates safety rules.
```

## Notes

- `artifact_id: ../../etc/passwd` is rejected because it contains path traversal and is not an opaque ID.
- The trusted producer must reject this **without reading the artifact**.
- The unsafe request asks for path traversal and secrets, but the wrapper report's `permission_escalation_requested: no` means the producer itself did not escalate permissions; the request was rejected before any escalation could occur.
- `verdict: GO` in the wrapper report is required by the existing report schema and is **not** part of the rejection response.
