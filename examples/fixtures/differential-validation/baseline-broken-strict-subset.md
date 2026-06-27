---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-strict-subset
agent_name: ProbeRunner
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/baseline-broken-strict-subset.md
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

# Fixture — BASELINE_BROKEN (strict subset) contrasted with GO

Base fails with 3 fingerprints. Candidate fails with a strict subset (1 of 3). `candidate_only` is empty → `BASELINE_BROKEN`. Contrast with the companion case where the candidate passes → `GO`.

## Case A: Candidate fails with strict subset → BASELINE_BROKEN

```yaml
# Base: 3 failures
# Candidate: 1 failure (subset of base)
failure_fingerprints:
  base:
    - "tests/test_subset.py:10:AssertionError"
    - "tests/test_subset.py:20:TypeError"
    - "tests/test_subset.py:30:KeyError"
  candidate:
    - "tests/test_subset.py:10:AssertionError"
```

- `base_only` = {`:20:TypeError`, `:30:KeyError`} → 2
- `candidate_only` = {} → 0
- `shared` = {`:10:AssertionError`} → 1

Step 6: both fail, `candidate_only` empty → `BASELINE_BROKEN`.

## Case B: Candidate passes → GO (contrast)

```yaml
# Same base, but candidate passes
failure_fingerprints:
  base:
    - "tests/test_subset.py:10:AssertionError"
    - "tests/test_subset.py:20:TypeError"
    - "tests/test_subset.py:30:KeyError"
  candidate: []
candidate_exit_code: 0
```

Step 3: `candidate_exit_code == 0` → `GO`. `base_only` = 3 records the removed debt.

## Differential Status Object (Case A)

```yaml
task_id: h4-fixture-strict-subset
profile: unit_targeted
selector: tests/test_subset.py
base_revision: aaa1111bbb2222
candidate_revision: bbb2222ccc3333
base_exit_code: 1
candidate_exit_code: 1
failure_fingerprints:
  base:
    - "tests/test_subset.py:10:AssertionError"
    - "tests/test_subset.py:20:TypeError"
    - "tests/test_subset.py:30:KeyError"
  candidate:
    - "tests/test_subset.py:10:AssertionError"
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-unit-ss-001"
differential_status: BASELINE_BROKEN
reason_code: candidate_strict_subset_of_baseline_failures
fingerprint_comparison:
  base_only: 2
  candidate_only: 0
  shared: 1
evidence_refs:
  - "artifact-unit-ss-001"
binding_metadata:
  selector_normalized: "tests/test_subset.py"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`BASELINE_BROKEN` — candidate fails but introduces no new failures (strict subset of base).

## Decisive rule

Step 6: both fail, `candidate_only == 0` → `BASELINE_BROKEN`. Contrast: if `candidate_exit_code == 0`, step 3 → `GO`.
