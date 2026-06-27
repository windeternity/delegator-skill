# Validation Catalog v0.1 — Profiles, Requests, and Compact Probe Evidence

This document is an **extension note** for the `agent-file-coordination` protocol. It builds on `references/protocol-spec-v0.1.md` (H1) and does not replace `references/task-report-schema.md` or change existing schema identifiers. All concepts defined here are **optional**.

## Purpose

Worker reports are untrusted explanations. The Validation Catalog provides:
1. A **coordinator-owned catalog** of opaque validation profiles.
2. A **declarative Validation Request** that workers may submit within coordinator-authorized bounds.
3. A **Compact Probe Evidence** format that trusted scripts, probes, or external adapters produce.

The coordinator authorizes profiles in the Task Bundle. The worker requests validation intent. A trusted producer executes the concrete command and emits compact evidence.

## Separation of concerns

| Layer | Owner | Content |
|---|---|---|
| Catalog | Coordinator / maintainer | Profile definitions, allowed selectors, safety rules |
| Task Bundle | Coordinator | `validation_profiles` list authorizing which profiles may be used for this task |
| Validation Request | Worker (bounded) | `profile`, `selector`, `reason` — only within the authorized profile list |
| Compact Probe Evidence | Trusted script / probe / adapter | `exit_codes`, `failure_fingerprints`, `artifact_ids` — produced by the runner, not the worker |

Workers must not pass executable command strings in requests or reports.

## Validation profiles

A profile is an **opaque label** mapped to a concrete command by the catalog. The coordinator decides which profiles are authorized for a task via `validation_profiles` in the Task Bundle.

### Catalog entries

| Profile | Purpose | Typical selector | Unsafe selector examples (prohibited) |
|---|---|---|---|
| `lint` | Static analysis / linting | File path or directory | Shell wildcards with recursion (`**/*`), pipe characters, environment variable expansion |
| `typecheck` | Type-system check | Package or module name | Shell command substitution, path traversal (`../`) |
| `unit_targeted` | Unit tests for changed files | Test file path | Arbitrary shell flags (`-rf`, `; rm`), glob injection |
| `unit_changed` | Unit tests selected by diff | Diff-relative path | Command chaining (`&&`, `\|\|`), subshells |
| `build_smoke` | Minimal build verification | Build target name | Absolute paths outside workspace, network URLs |

### Selector safety rules

- Selectors must be **relative paths, package names, or build targets**.
- Selectors must not contain shell metacharacters: `;`, `|`, `&`, `$`, `` ` ``, `\`, `*`, `?`, `<`, `>`.
- Selectors must not contain path traversal sequences (`../`, `..\`).
- Selectors use **normalized workspace-relative `/` paths on every platform**, including Windows. A selector such as `scripts/validate.py` is valid on both POSIX and Windows.
- Selectors must not start with `-` (to prevent flag injection).
- If a selector violates these rules, the trusted producer must reject the request without executing it.

## Validation Request

A worker may submit a Validation Request when it believes a validation check is relevant. The request must stay within the coordinator-authorized profile list.

### Request fields

| Field | Type | Required | Description |
|---|---|---|---|
| `profile` | string | yes | Must be one of the profiles listed in the Task Bundle `validation_profiles`. |
| `selector` | string | no | Safe selector as defined above. Omit if the profile does not need one. |
| `reason` | string | yes | Short human-readable reason for the request. |

### Example: allowed request

```yaml
profile: lint
selector: scripts/
reason: Changed files in scripts/ may have style violations.
```

### Example: rejected out-of-catalog request

If the Task Bundle authorizes only `lint` and `typecheck`, a worker request for `build_smoke` is out of bounds. The trusted producer must reject it:

```yaml
profile: build_smoke
selector: .
reason: Want to verify the build still passes.
```

Rejection response (compact evidence):

```yaml
profile: build_smoke
status: rejected
reason: Profile not authorized in Task Bundle validation_profiles.
```

The `status: rejected` field is a producer-internal status, not a coordinator verdict. It records that the trusted producer refused to execute the request.

## Compact Probe Evidence

Compact Probe Evidence is produced by a trusted script, probe, or external adapter — not by the worker. It binds validation results to a specific task, base, and candidate.

### Evidence fields

| Field | Type | Required | Description |
|---|---|---|---|
| `task_id` | string | yes | Must match the task file `task_id`. |
| `base_sha` | string | yes | Git SHA or content hash of the base revision. |
| `candidate_sha` | string | yes | Git SHA or content hash of the candidate revision. |
| `diff_hash` | string | no | Hash of the diff between base and candidate. |
| `profile` | string | yes | Profile that was executed. |
| `selector` | string | no | Selector used, if any. |
| `base_exit_code` | integer | yes | Exit code from running the profile against base. |
| `candidate_exit_code` | integer | yes | Exit code from running the profile against candidate. |
| `failure_fingerprints` | object | no | Side-bound failure summaries with keys `base` and `candidate`, each a list of strings (e.g., `file:line:rule_id`). |
| `artifact_ids` | list of strings | no | References to full logs, patches, or screenshots stored in an artifact store. |

### Rules

- `failure_fingerprints` must be an object with `base` and `candidate` keys, each containing a list of deterministic failure summaries. This allows differential comparison without adding H4 verdict taxonomy.
- `artifact_ids` must not be arbitrary file paths; they are opaque IDs in a trusted artifact store.
- Evidence does not include verdicts such as `GO`, `REGRESSION`, `BASELINE_BROKEN`. Verdict assignment is coordinator-owned and defined in H4.
- Evidence does not include shell command strings.

### Example: compact evidence

```yaml
task_id: h2-example-evidence
base_sha: abc1234
candidate_sha: def5678
diff_hash: sha256:9f86d08...
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

## Backward compatibility

- Existing `agent-file-coordination/*` schema identifiers remain unchanged.
- `schema_version: 0.1.0` remains valid.
- Unknown frontmatter keys are ignored by `validate-agent-inbox.py`.
- Task files without validation profiles or evidence are still fully valid.

## Non-goals

- This document does not define Evidence Expansion (H3).
- This document does not define differential validation taxonomy or verdicts such as `GO`, `REGRESSION`, `PARTIAL_REGRESSION`, `BASELINE_BROKEN`, `FLAKY_SUSPECT`, `INCONCLUSIVE` (H4).
- This document does not implement probes, runners, Docker, daemons, or adapters.
- This document does not add mandatory runtime behavior.
