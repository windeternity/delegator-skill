---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-partial-regression
agent_name: ProbeRunner
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/status-partial-regression.md
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

# Fixture — PARTIAL_REGRESSION

Baseline already fails; candidate removes some baseline failures but introduces new ones. Expected status: `PARTIAL_REGRESSION`.

## Differential Status Object

```yaml
task_id: h4-fixture-partial-regression
profile: unit_targeted
selector: tests/test_io.py
base_revision: aaa1111bbb2222
candidate_revision: bbb2222ccc3333
base_exit_code: 1
candidate_exit_code: 1
failure_fingerprints:
  base:
    - "tests/test_io.py:10:FileNotFoundError"
    - "tests/test_io.py:25:TimeoutError"
  candidate:
    - "tests/test_io.py:25:TimeoutError"
    - "tests/test_io.py:60:AssertionError"
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-unit-pr-001"
differential_status: PARTIAL_REGRESSION
reason_code: baseline_broken_candidate_adds_new_failures
fingerprint_comparison:
  base_only: 1
  candidate_only: 1
  shared: 1
evidence_refs:
  - "artifact-unit-pr-001"
binding_metadata:
  selector_normalized: "tests/test_io.py"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`PARTIAL_REGRESSION` — baseline broken, candidate removed 1 failure (`base_only: 1`), added 1 new failure (`candidate_only: 1`), 1 shared.

## Decisive rule

Step 5: both fail, `candidate_only > 0` → `PARTIAL_REGRESSION`.
