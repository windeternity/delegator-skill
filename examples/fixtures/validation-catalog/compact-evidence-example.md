---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: h2-fixture-evidence-example
agent_name: Probe
verdict: GO
changed_files:
  - none
evidence_refs:
  - examples/fixtures/validation-catalog/compact-evidence-example.md
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

# Compact Probe Evidence Example

This file demonstrates the Compact Probe Evidence format defined in `references/validation-catalog-v0.1.md`. It is a report fixture that a trusted probe might produce.

## Evidence

```yaml
task_id: h2-fixture-evidence-example
base_sha: abc1234def5678
candidate_sha: def5678abc1234
diff_hash: sha256:9f86d0848849c5c8e5f0f9f5f5e5d5c5b5a5f5e5d5c5b5a5948f7e6d5c4b3a2f1e0
profile: lint
selector: scripts/
base_exit_code: 0
candidate_exit_code: 1
failure_fingerprints:
  base: []
  candidate:
    - "scripts/validate.py:42:E501"
    - "scripts/validate.py:55:W291"
artifact_ids:
  - "artifact-lint-001"
```

## Notes

- `failure_fingerprints` are side-bound (`base` and `candidate`) for differential comparison.
- `artifact_ids` are opaque references to an artifact store, not file paths.
- No shell command strings appear in this evidence.
- No verdict taxonomy (`GO`, `REGRESSION`, etc.) is included; that is H4 scope.
- The wrapper report's `verdict: GO` is required by the existing report schema and is not part of Compact Probe Evidence.
