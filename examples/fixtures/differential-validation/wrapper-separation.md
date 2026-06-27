---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-wrapper-separation
agent_name: ProbeRunner
verdict: PARTIAL
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/wrapper-separation.md
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

# Fixture — Wrapper Separation

Demonstrates that `differential_status` is **not** the report `verdict`, task `status`, or coordinator verdict.

**Note**: This fixture uses a report wrapper with `verdict: PARTIAL` and a task lifecycle of `ASSIGNED` for illustrative purposes. In a real coordination run, the task file would be a separate `.md` in `.agent-inbox/` with its own frontmatter; the report wrapper here simulates that separation. The key point is that these three values are independent concepts owned by different layers.

## Three independent values

| Field | Value | Owner | Source |
|---|---|---|---|
| Report `verdict` | `PARTIAL` | Worker self-assessment (untrusted) | This wrapper's frontmatter |
| Task lifecycle `status` | `ASSIGNED` | Protocol schema | Would be in the task file's frontmatter |
| `differential_status` | `GO` | H4 classification of trusted H2 evidence | The object below |

These three are independent concepts and must not be conflated.

## Differential Status Object

```yaml
task_id: h4-fixture-wrapper-separation
profile: unit_targeted
selector: tests/test_boundary.py
base_revision: aaa1111bbb2222
candidate_revision: bbb2222ccc3333
base_exit_code: 1
candidate_exit_code: 0
failure_fingerprints:
  base:
    - "tests/test_boundary.py:10:AssertionError"
  candidate: []
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-unit-wrap-001"
differential_status: GO
reason_code: candidate_passes
fingerprint_comparison:
  base_only: 1
  candidate_only: 0
  shared: 0
evidence_refs:
  - "artifact-unit-wrap-001"
binding_metadata:
  selector_normalized: "tests/test_boundary.py"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`GO` (differential) — candidate passes (step 3). Removed 1 baseline failure.

## Wrapper/differential separation

- Report `verdict: PARTIAL` — worker's self-assessment (may be wrong; coordinator decides).
- `differential_status: GO` — trusted H2 evidence shows candidate passes (step 3 of the ordered decision procedure).
- Task `status: ASSIGNED` — lifecycle state, unrelated to evidence classification.
- The coordinator uses `differential_status` as **input evidence** to the 14-point rubric, not as the final verdict.

## Decisive rule

Step 3: `candidate_exit_code == 0` → `GO`. Report `verdict` and task lifecycle are separate concerns.
