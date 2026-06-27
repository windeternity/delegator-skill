---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-go-removes
agent_name: ProbeRunner
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/status-go-removes-failures.md
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

# Fixture — GO (candidate removes baseline failures)

Base fails, candidate passes. The candidate removed baseline debt. Expected status: `GO`, not `BASELINE_BROKEN`.

## Differential Status Object

```yaml
task_id: h4-fixture-go-removes
profile: unit_targeted
selector: tests/test_parser.py
base_revision: aaa1111bbb2222
candidate_revision: bbb2222ccc3333
base_exit_code: 1
candidate_exit_code: 0
failure_fingerprints:
  base:
    - "tests/test_parser.py:10:AssertionError"
    - "tests/test_parser.py:22:TypeError"
  candidate: []
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-unit-go-002"
differential_status: GO
reason_code: candidate_passes
fingerprint_comparison:
  base_only: 2
  candidate_only: 0
  shared: 0
evidence_refs:
  - "artifact-unit-go-002"
binding_metadata:
  selector_normalized: "tests/test_parser.py"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`GO` — candidate passes (step 3). Removed 2 baseline failures. `base_only > 0` records the debt that was cleared.

## Decisive rule

Step 3: `candidate_exit_code == 0` → `GO`. Not `BASELINE_BROKEN` because the candidate passes.
