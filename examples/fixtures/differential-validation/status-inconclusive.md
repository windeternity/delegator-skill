---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h4-fixture-inconclusive
agent_name: ProbeRunner
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/differential-validation/status-inconclusive.md
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

# Fixture — INCONCLUSIVE (profile not in authorized list)

One H2 Compact Probe Evidence object has `profile: lint`, but the task's authorized `validation_profiles` only contains `unit_targeted`. The H4 consumer detects this during step 1 binding validation against the task file. Expected status: `INCONCLUSIVE`.

## Binding validation

H2 emits **one** Compact Probe Evidence object with both `base_exit_code` and `candidate_exit_code`. The H4 consumer compares the H2 object's `profile` field against the task's authorized `validation_profiles`:

| Validation | H2 value | Task authorized list | Match? |
|---|---|---|---|
| `task_id` | `h4-fixture-inconclusive` | `h4-fixture-inconclusive` | yes |
| `profile` | `lint` | `[unit_targeted]` | **no** |
| `selector` | `scripts/` | — | present |
| `base_sha` | `aaa1111bbb2222` | — | present |
| `candidate_sha` | `bbb2222ccc3333` | — | present, distinct |
| `base_exit_code` | `0` | — | valid |
| `candidate_exit_code` | `1` | — | valid |
| `failure_fingerprints.base` | `[]` | — | consistent with exit 0 |
| `failure_fingerprints.candidate` | `["scripts/validate.py:42:E501"]` | — | consistent with exit 1 |
| `producer_id` | `probe-runner-v1.0` | — | trusted, not worker |

The single H2 object is internally consistent (exit codes match fingerprints), but its `profile` is not authorized by the task.

## Differential Status Object

```yaml
task_id: h4-fixture-inconclusive
profile: lint
selector: scripts/
base_revision: aaa1111bbb2222
candidate_revision: bbb2222ccc3333
base_exit_code: 0
candidate_exit_code: 1
failure_fingerprints:
  base: []
  candidate:
    - "scripts/validate.py:42:E501"
producer_id: probe-runner-v1.0
evidence_binding:
  artifact_ids:
    - "artifact-lint-inc-001"
differential_status: INCONCLUSIVE
reason_code: profile_not_in_authorized_validation_profiles
evidence_refs:
  - "artifact-lint-inc-001"
binding_metadata:
  selector_normalized: "scripts/"
  fingerprint_order_invariant: true
  comparison_method: set
```

## Expected classification

`INCONCLUSIVE` — step 1: `profile` not in task's authorized `validation_profiles`.

## Decisive rule

Step 1: H2 object's `profile: lint` is not in the task's `validation_profiles: [unit_targeted]` → `INCONCLUSIVE`. This is a single H2 object with an unauthorized profile, not two separate objects.
