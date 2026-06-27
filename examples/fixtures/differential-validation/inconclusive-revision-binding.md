---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-revision-binding
agent_name: ProbeRunner
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/inconclusive-revision-binding.md
evidence_trust:
  trust_level: blocked_or_suspicious
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
  tier: targeted-test
  result: pass
reported_at: 2026-06-11
---

# Fixture — INCONCLUSIVE (revision binding failure)

`base_revision` is empty. This violates the requirement that both revisions must be non-empty and distinct. Expected status: `INCONCLUSIVE`.

## Binding validation inputs

| Field | Value | Valid? |
|---|---|---|
| `task_id` | `h4-fixture-revision-binding` | yes |
| `profile` | `unit_targeted` | yes |
| `selector` | `tests/test_rev.py` | yes |
| `base_revision` | `""` (empty) | **no**: must be non-empty |
| `candidate_revision` | `bbb2222ccc3333` | yes |
| `producer_id` | `probe-runner-v1.0` | yes |

## Differential Status Object

```yaml
task_id: h4-fixture-revision-binding
profile: unit_targeted
selector: tests/test_rev.py
base_revision: ""
candidate_revision: bbb2222ccc3333
base_exit_code: 0
candidate_exit_code: 1
failure_fingerprints:
  base: []
  candidate:
    - "tests/test_rev.py:15:AssertionError"
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-unit-rb-001"
binding_validation:
  task_id_match: yes
  profile_match: yes
  selector_match: yes
  base_revision_valid: no
  base_revision_reason: empty
  candidate_revision_valid: yes
  producer_match: yes
differential_status: INCONCLUSIVE
reason_code: binding_invalid_base_revision_empty
evidence_refs:
  - "artifact-unit-rb-001"
binding_metadata:
  selector_normalized: "tests/test_rev.py"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`INCONCLUSIVE` — step 1: `base_revision` is empty.

## Decisive rule

Step 1: `base_revision` absent or empty → `INCONCLUSIVE`. Also covers the case where `base_revision == candidate_revision` (identical revisions → unverifiable comparison).
