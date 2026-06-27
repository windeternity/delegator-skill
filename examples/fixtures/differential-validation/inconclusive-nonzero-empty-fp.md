---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-nonzero-empty
agent_name: ProbeRunner
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/inconclusive-nonzero-empty-fp.md
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

# Fixture — INCONCLUSIVE (non-zero exit + empty fingerprints)

Candidate has exit code 1 but an empty fingerprint list. This is a contradiction per rule E3. Expected status: `INCONCLUSIVE`.

## Preflight violation

| Rule | Field | Value | Violation? |
|---|---|---|---|
| E3 | `candidate_exit_code` | `1` | — |
| E3 | `failure_fingerprints.candidate` | `[]` | **yes**: non-zero exit code requires non-empty fingerprints |

An empty list `[]` means green **only** when the exit code is `0`. Exit code `1` with `[]` is a contradiction.

## Differential Status Object

```yaml
task_id: h4-fixture-nonzero-empty
profile: unit_targeted
selector: tests/test_edge.py
base_revision: aaa1111bbb2222
candidate_revision: bbb2222ccc3333
base_exit_code: 0
candidate_exit_code: 1
failure_fingerprints:
  base: []
  candidate: []
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-unit-nze-001"
preflight_violation:
  rule: E3
  field: failure_fingerprints.candidate
  value: []
  reason: Non-zero exit code (1) with empty fingerprint list
differential_status: INCONCLUSIVE
reason_code: exit_code_fingerprint_contradiction
evidence_refs:
  - "artifact-unit-nze-001"
binding_metadata:
  selector_normalized: "tests/test_edge.py"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`INCONCLUSIVE` — step 1 preflight failure (rule E3).

## Decisive rule

Step 1: `candidate_exit_code == 1` and `failure_fingerprints.candidate == []` → rule E3 violation → `INCONCLUSIVE`.
