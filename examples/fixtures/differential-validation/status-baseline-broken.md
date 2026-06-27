---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-baseline-broken
agent_name: ProbeRunner
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/status-baseline-broken.md
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
  tier: targeted-test
  result: pass
reported_at: 2026-06-11
---

# Fixture — BASELINE_BROKEN

Baseline fails; candidate fails with identical fingerprints (debt unchanged). Expected status: `BASELINE_BROKEN`.

## Differential Status Object

```yaml
task_id: h4-fixture-baseline-broken
profile: unit_targeted
selector: tests/test_legacy.py
base_revision: aaa1111bbb2222
candidate_revision: bbb2222ccc3333
base_exit_code: 1
candidate_exit_code: 1
failure_fingerprints:
  base:
    - "tests/test_legacy.py:33:DeprecationWarning"
    - "tests/test_legacy.py:44:AssertionError"
  candidate:
    - "tests/test_legacy.py:33:DeprecationWarning"
    - "tests/test_legacy.py:44:AssertionError"
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-unit-bb-001"
differential_status: BASELINE_BROKEN
reason_code: broken_baseline_no_new_candidate_failures
fingerprint_comparison:
  base_only: 0
  candidate_only: 0
  shared: 2
evidence_refs:
  - "artifact-unit-bb-001"
binding_metadata:
  selector_normalized: "tests/test_legacy.py"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`BASELINE_BROKEN` — baseline debt unchanged; candidate introduces no new failures.

## Decisive rule

Step 6: both fail, `candidate_only == 0` → `BASELINE_BROKEN`.
