---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-regression
agent_name: ProbeRunner
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/status-regression.md
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

# Fixture — REGRESSION

Base passes (green), candidate fails with new fingerprints. Expected status: `REGRESSION`.

## Differential Status Object

```yaml
task_id: h4-fixture-regression
profile: unit_targeted
selector: tests/test_serializer.py
base_revision: aaa1111bbb2222
candidate_revision: bbb2222ccc3333
base_exit_code: 0
candidate_exit_code: 1
failure_fingerprints:
  base: []
  candidate:
    - "tests/test_serializer.py:55:KeyError"
    - "tests/test_serializer.py:78:AssertionError"
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-unit-reg-001"
differential_status: REGRESSION
reason_code: green_base_candidate_introduces_failures
fingerprint_comparison:
  base_only: 0
  candidate_only: 2
  shared: 0
evidence_refs:
  - "artifact-unit-reg-001"
binding_metadata:
  selector_normalized: "tests/test_serializer.py"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`REGRESSION` — green baseline broken by candidate with 2 new failures.

## Decisive rule

Step 4: `base_exit_code == 0`, `candidate_exit_code != 0` → `REGRESSION`.
