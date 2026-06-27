---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-flaky
agent_name: ProbeRunner
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/status-flaky-suspect.md
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

# Fixture — FLAKY_SUSPECT

Repeated runs show instability on the candidate side. Expected status: `FLAKY_SUSPECT`.

## Differential Status Object

```yaml
task_id: h4-fixture-flaky
profile: unit_targeted
selector: tests/test_network.py
base_revision: aaa1111bbb2222
candidate_revision: bbb2222ccc3333
base_exit_code: 0
candidate_exit_code: 1
failure_fingerprints:
  base: []
  candidate:
    - "tests/test_network.py:88:ConnectionError"
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-unit-flaky-001"
representative_run_number: 1
repeat_observations:
  - run_number: 1
    base_exit_code: 0
    candidate_exit_code: 1
    base_fingerprints: []
    candidate_fingerprints:
      - "tests/test_network.py:88:ConnectionError"
  - run_number: 2
    base_exit_code: 0
    candidate_exit_code: 0
    base_fingerprints: []
    candidate_fingerprints: []
  - run_number: 3
    base_exit_code: 0
    candidate_exit_code: 1
    base_fingerprints: []
    candidate_fingerprints:
      - "tests/test_network.py:88:ConnectionError"
differential_status: FLAKY_SUSPECT
reason_code: candidate_side_unstable_across_runs
fingerprint_comparison:
  base_only: 0
  candidate_only: 1
  shared: 0
evidence_refs:
  - "artifact-unit-flaky-001"
binding_metadata:
  selector_normalized: "tests/test_network.py"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`FLAKY_SUSPECT` — candidate exit code alternates between 0 and 1 across 3 runs; base is stable.

## Decisive rule

Step 2: `repeat_observations` present with ≥ 2 valid observations, candidate side shows different exit codes → `FLAKY_SUSPECT`. Without repeats, step 4 would fire (`REGRESSION`); repeats reveal instability first.
