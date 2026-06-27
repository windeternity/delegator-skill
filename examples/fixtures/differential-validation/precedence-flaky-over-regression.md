---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-precedence
agent_name: ProbeRunner
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/precedence-flaky-over-regression.md
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

# Fixture — Precedence: FLAKY_SUSPECT wins over REGRESSION

Single-run snapshot looks like `REGRESSION` (green base, failing candidate), but repeat observations show instability. `FLAKY_SUSPECT` has higher precedence than `REGRESSION`.

## Single-run snapshot (would be REGRESSION without repeats)

```yaml
# This is what a single run would show:
base_exit_code: 0
candidate_exit_code: 1
failure_fingerprints:
  base: []
  candidate:
    - "tests/test_flaky_edge.py:12:TimeoutError"
```

Without repeat observations, this would classify as `REGRESSION`.

## Differential Status Object (with repeats)

```yaml
task_id: h4-fixture-precedence
profile: unit_targeted
selector: tests/test_flaky_edge.py
base_revision: aaa1111bbb2222
candidate_revision: bbb2222ccc3333
base_exit_code: 0
candidate_exit_code: 1
failure_fingerprints:
  base: []
  candidate:
    - "tests/test_flaky_edge.py:12:TimeoutError"
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-unit-prec-001"
representative_run_number: 1
repeat_observations:
  - run_number: 1
    base_exit_code: 0
    candidate_exit_code: 1
    base_fingerprints: []
    candidate_fingerprints:
      - "tests/test_flaky_edge.py:12:TimeoutError"
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
      - "tests/test_flaky_edge.py:12:TimeoutError"
differential_status: FLAKY_SUSPECT
reason_code: candidate_side_unstable_overrides_single_run_regression
fingerprint_comparison:
  base_only: 0
  candidate_only: 1
  shared: 0
evidence_refs:
  - "artifact-unit-prec-001"
binding_metadata:
  selector_normalized: "tests/test_flaky_edge.py"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`FLAKY_SUSPECT` — not `REGRESSION`.

## Decisive rule

Ordered decision procedure: step 1 preflight passes → step 2 detects instability in repeat observations → `FLAKY_SUSPECT`. Step 4 (`REGRESSION`) is never reached because step 2 fires first. The ordered procedure ensures no input can match both statuses.
