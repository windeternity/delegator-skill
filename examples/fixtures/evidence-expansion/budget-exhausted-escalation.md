---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h3-fixture-budget-exhausted
agent_name: ArtifactReader
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/evidence-expansion/budget-exhausted-escalation.md
evidence_trust:
  trust_level: reproduced
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
reported_at: 2026-06-11
---

# Fixture — Bounded Truncation with Escalation Recommendation

This fixture demonstrates what happens when a valid, authorized request asks for a window larger than the per-request size budget: the producer returns a bounded, truncated response. If the truncated slice is insufficient for the decision gap, the producer appends an `ESCALATED` recommendation.

## Expansion Request (valid but large)

```yaml
task_id: h3-fixture-budget-exhausted
artifact_id: artifact-lint-001
reason: Need the lint output around the failure fingerprint to write a fix.
requested_window:
  form: fingerprint_neighborhood
  fingerprint: "scripts/validate.py:42:E501"
  context_lines: 10
max_bytes: 2048
max_tokens: 512
request_number: 2
request_limit: 3
```

## Trusted Expansion Response (truncated)

```yaml
task_id: h3-fixture-budget-exhausted
artifact_id: artifact-lint-001
request_number: 2
content_hash: sha256:c5d7e9f4b3a1...
window_returned:
  form: fingerprint_neighborhood
  fingerprint: "scripts/validate.py:42:E501"
  context_lines: 5
bytes_returned: 2048
tokens_estimated: 512
truncated: yes
truncation_boundary: byte_limit
last_included_line: 47
content_excerpt: |
  def validate_selector(selector):
      if not selector:
          raise ValueError("Selector must not be empty")
      if ".." in selector:
          raise ValueError("Path traversal detected")
      return selector
estimation_method: byte_ratio_4
untrusted_content_present: no
prompt_injection_markers_detected: no
producer_id: artifact-reader-v1.2
recommendation: ESCALATED
recommendation_reason: Truncated slice ends before the fingerprint neighborhood context needed to resolve the decision gap; human or higher-trust review required.
```

## Notes

- `truncated: yes` means the response stopped at a size limit; the request itself was valid.
- `recommendation: ESCALATED` is advisory because the returned slice is insufficient for the coordinator's decision gap.
- The coordinator may issue another expansion request if `request_number` is still within `request_limit`.
- `verdict: GO` in the wrapper report is required by the existing report schema and is **not** part of the Trusted Expansion Response.
