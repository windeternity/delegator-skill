---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-stable-repeat
agent_name: ProbeRunner
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/stable-repeat-continues.md
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

# Fixture — Stable repeat observations continue to REGRESSION

Repeat observations are present and **stable** (all agree). Step 2 is skipped; classification continues to step 4 (`REGRESSION`). Expected status: `REGRESSION`.

## Repeat stability check

| Run | Base exit | Candidate exit | Base FP | Candidate FP |
|---|---|---|---|---|
| 1 | 0 | 1 | [] | [tests/test_stable.py:20:ValueError] |
| 2 | 0 | 1 | [] | [tests/test_stable.py:20:ValueError] |
| 3 | 0 | 1 | [] | [tests/test_stable.py:20:ValueError] |

All 3 runs agree: base passes, candidate fails with the same fingerprint. No instability → skip step 2.

## Differential Status Object

```yaml
task_id: h4-fixture-stable-repeat
profile: unit_targeted
selector: tests/test_stable.py
base_revision: aaa1111bbb2222
candidate_revision: bbb2222ccc3333
base_exit_code: 0
candidate_exit_code: 1
failure_fingerprints:
  base: []
  candidate:
    - "tests/test_stable.py:20:ValueError"
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-unit-sr-001"
representative_run_number: 1
repeat_observations:
  - run_number: 1
    base_exit_code: 0
    candidate_exit_code: 1
    base_fingerprints: []
    candidate_fingerprints:
      - "tests/test_stable.py:20:ValueError"
  - run_number: 2
    base_exit_code: 0
    candidate_exit_code: 1
    base_fingerprints: []
    candidate_fingerprints:
      - "tests/test_stable.py:20:ValueError"
  - run_number: 3
    base_exit_code: 0
    candidate_exit_code: 1
    base_fingerprints: []
    candidate_fingerprints:
      - "tests/test_stable.py:20:ValueError"
differential_status: REGRESSION
reason_code: stable_repeats_green_base_candidate_fails
fingerprint_comparison:
  base_only: 0
  candidate_only: 1
  shared: 0
evidence_refs:
  - "artifact-unit-sr-001"
binding_metadata:
  selector_normalized: "tests/test_stable.py"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`REGRESSION` — stable repeats confirm the single-run result; step 2 skipped, step 4 fires.

## Decisive rule

Step 1: preflight passes. Step 2: repeats are stable → skip. Step 3: `candidate_exit_code != 0` → no. Step 4: `base_exit_code == 0` → `REGRESSION`.
