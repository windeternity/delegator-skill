---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h3-fixture-trusted-response
agent_name: ArtifactReader
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/evidence-expansion/trusted-expansion-response.md
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

# Fixture — Trusted Expansion Response

This fixture demonstrates a valid Trusted Expansion Response produced by a trusted artifact reader.

## Trusted Expansion Response

```yaml
task_id: h3-fixture-bounded-request
artifact_id: artifact-lint-001
request_number: 1
content_hash: sha256:a3f5c8e9d2b1...
window_returned:
  form: line_range
  start_line: 40
  end_line: 45
bytes_returned: 512
tokens_estimated: 128
truncated: no
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
```

## Notes

- `verdict: GO` in the wrapper report is required by the existing report schema and is **not** part of the Trusted Expansion Response.
- `window_returned` may be smaller than `requested_window` if the artifact is shorter.
- `content_excerpt` is bounded and does not exceed the request's `max_bytes` / `max_tokens`.
- `prompt_injection_markers_detected: no` means no red-flag patterns were found.
