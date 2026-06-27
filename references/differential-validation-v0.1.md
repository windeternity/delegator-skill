# Differential Validation Taxonomy v0.1

This document is an **extension note** for the `agent-file-coordination` protocol. It builds on `references/validation-catalog-v0.1.md` (H2) and `references/evidence-expansion-v0.1.md` (H3). It does not replace existing schemas or change schema identifiers. All concepts defined here are **optional**.

## Purpose

Real projects may have broken baselines or flaky tests. Absolute test failure can wrongly punish a worker for historical debt. Differential validation compares trusted H2 base/candidate evidence **without assuming a green baseline**, producing a compact classification that informs — but does not replace — the coordinator's final verdict.

## Separation of concerns

| Concept | Owner | H4 relationship |
|---|---|---|
| Task lifecycle state (`ASSIGNED`, `REPORTED`, …) | Protocol schema | Unchanged. `differential_status` is not a lifecycle value. |
| Report `verdict` (`GO` / `PARTIAL` / `RED`) | Worker self-assessment | Unchanged. `differential_status` does not replace or override it. |
| Coordinator verdict (`GO` / `PARTIAL` / `RED`) | Coordinator rubric (14-point) | Unchanged. `differential_status` is input evidence, not final judgment. |
| H2 producer `status: rejected` | Trusted producer | Unchanged. H4 does not overload producer-internal statuses. |
| H3 `recommendation` (`BLOCKED` / `ESCALATED`) | Trusted expansion producer | Unchanged. H4 does not overload expansion recommendations. |
| `differential_status` | H4 taxonomy (this document) | Optional classification of trusted H2 evidence. |

## H2 field alignment

H2 v0.1 emits one Compact Probe Evidence object containing: `task_id`, `base_sha`, `candidate_sha`, `profile`, optional `selector`, `base_exit_code`, `candidate_exit_code`, `failure_fingerprints` (with `base` and `candidate` keys), and optional `artifact_ids`.

H4 consumes these fields **by name**. The mapping is:

| H4 input | H2 source | Notes |
|---|---|---|
| `task_id` | `task_id` | Direct copy. |
| `profile` | `profile` | Direct copy. |
| `selector` | `selector` | Direct copy; may be absent if profile does not require one. |
| `base_revision` | `base_sha` | Direct copy. |
| `candidate_revision` | `candidate_sha` | Direct copy. |
| `base_exit_code` | `base_exit_code` | Direct copy. |
| `candidate_exit_code` | `candidate_exit_code` | Direct copy. |
| `failure_fingerprints` | `failure_fingerprints` | Direct copy; side-bound object with `base` and `candidate` keys. |
| `artifact_ids` | `artifact_ids` | Direct copy; may be absent. |
| `diff_hash` | `diff_hash` | Direct copy; optional. |
| `producer_id` | *not in H2 v0.1* | See below. |

### `producer_id` provenance

H2 v0.1 does not list `producer_id` as an evidence field. H4 introduces `producer_id` as **additive trusted-comparison metadata** that identifies which trusted script, probe, or adapter produced the H2 evidence. The coordinator or a trusted binding layer attaches this field when forwarding H2 evidence to H4 classification. It is **not** set by the worker.

Possible sources for `producer_id`:
- The trusted script's own identifier (e.g., `probe-runner-v1.0`).
- A CI job name or workflow step ID.
- An adapter-registered name from the validation catalog.

If `producer_id` cannot be determined, the evidence is classified `INCONCLUSIVE` because provenance is unverifiable.

## Exit-code / fingerprint consistency preflight

Before any differential comparison, the following **deterministic preflight rules** must hold. Violation → `INCONCLUSIVE`.

| Rule | Description |
|---|---|
| E1 | Exit code `0` requires an **explicitly present, empty** fingerprint list (`[]`) for that side. |
| E2 | Non-zero exit code requires an **explicitly present, non-empty** fingerprint list for that side. |
| E3 | A non-zero exit code with an **empty** fingerprint list (`[]`) is a contradiction → `INCONCLUSIVE`. |
| E4 | A non-zero exit code with a **missing** fingerprint key is a contradiction → `INCONCLUSIVE`. |
| E5 | An exit code `0` with a **missing** fingerprint key is a contradiction → `INCONCLUSIVE`. |
| E6 | Timeout, unknown exit codes, or non-integer exit codes → `INCONCLUSIVE`. |
| E7 | "Field absent" (key missing from the object) is **not** the same as "present and empty" (`[]`). An absent key is always `INCONCLUSIVE`. |

An empty list `[]` means green **only** when the corresponding exit code is `0`. An empty list with a non-zero exit code must never be treated as green.

## Differential Status Object

A compact, optional classification that consumes trusted H2 Compact Probe Evidence.

### Required inputs

| Input | Type | Description |
|---|---|---|
| `task_id` | string | Must match the task file `task_id`. |
| `profile` | string | Must match the H2 evidence `profile` and the task's authorized `validation_profiles`. |
| `selector` | string | Normalized workspace-relative selector, must match H2 evidence. May be absent if profile does not require one. |
| `base_revision` | string | Git SHA or content hash matching H2 `base_sha`. Must be non-empty and distinct from `candidate_revision`. |
| `candidate_revision` | string | Git SHA or content hash matching H2 `candidate_sha`. Must be non-empty and distinct from `base_revision`. |
| `base_exit_code` | integer | From H2 evidence `base_exit_code`. |
| `candidate_exit_code` | integer | From H2 evidence `candidate_exit_code`. |
| `failure_fingerprints` | object | Side-bound `{base: [...], candidate: [...]}` from H2 evidence. Both keys must be present with explicit lists. |
| `producer_id` | string | Identifier of the trusted H2 producer. Must not be the worker. See § producer_id provenance. |
| `evidence_binding` | object | References to H2 evidence artifacts (e.g., `artifact_ids`). |

### Optional inputs

| Input | Type | When used |
|---|---|---|
| `repeat_observations` | list of objects | Only for flake classification. See § Repeat observation binding. |
| `representative_run_number` | integer | Required when `repeat_observations` is present. 1-based index identifying which observation the top-level snapshot corresponds to. |
| `diff_hash` | string | From H2 evidence, for reproducibility binding. |

### Outputs

| Output | Type | Description |
|---|---|---|
| `differential_status` | string | Exactly one of: `GO`, `REGRESSION`, `PARTIAL_REGRESSION`, `BASELINE_BROKEN`, `FLAKY_SUSPECT`, `INCONCLUSIVE`. |
| `reason_code` | string | Concise machine-readable reason (e.g., `no_new_failures`, `candidate_introduces_failures`). |
| `fingerprint_comparison` | object | `{base_only: int, candidate_only: int, shared: int}` when comparison is valid. Omitted for `INCONCLUSIVE`. |
| `evidence_refs` | list of strings | Artifact IDs or references, not raw logs. |
| `binding_metadata` | object | Enough to reproduce why the status was selected: `selector_normalized`, `fingerprint_order_invariant: true`, `comparison_method: set`. |

## Ordered decision procedure

Classification is a **strictly ordered, single-pass procedure**. Evaluate steps 1–6 in order; the **first matching step wins**. No valid input can match more than one step.

```
Step 1: INCONCLUSIVE   — preflight failure, binding mismatch, untrusted producer, missing fields
Step 2: FLAKY_SUSPECT  — valid bound repeat observations with demonstrated instability
Step 3: GO             — candidate_exit_code == 0 (candidate passes, regardless of base state)
Step 4: REGRESSION     — base_exit_code == 0 AND candidate_exit_code != 0
Step 5: PARTIAL_REGRESSION — both fail AND candidate_only fingerprint set is non-empty
Step 6: BASELINE_BROKEN    — both fail AND candidate_only fingerprint set is empty
```

**Every valid input that passes step 1 preflight matches exactly one of steps 2–6.** The procedure is exhaustive and mutually exclusive by construction.

### Step 1: INCONCLUSIVE

Preflight and binding validation. **Any failure here → INCONCLUSIVE, stop.**

Triggers (any one is sufficient):
- Exit-code/fingerprint consistency violation (rules E1–E7 above).
- `task_id` mismatch between evidence and task file.
- `profile` mismatch between base and candidate evidence, or profile not in task's authorized `validation_profiles`.
- `selector` mismatch between base and candidate evidence (when selector is present).
- `base_revision` or `candidate_revision` absent, empty, or identical to each other.
- `base_revision` mismatch with H2 `base_sha`, or `candidate_revision` mismatch with H2 `candidate_sha`.
- `producer_id` absent, empty, or identifies the worker (self-authored evidence).
- `artifact_ids` present but contains IDs not found in the H2 evidence.
- Any required field is absent from the object.
- `repeat_observations` present with fewer than 2 valid comparable observations (see § Repeat observation binding).
- `repeat_observations` present but `representative_run_number` missing, invalid, or not matching any observation after normalization (see § Top-level snapshot vs repeats).

### Step 2: FLAKY_SUSPECT

**Precondition**: step 1 passed (all bindings valid, preflight clean).
**Condition**: `repeat_observations` is present with ≥ 2 valid comparable observations, and at least one side shows different exit codes or different normalized fingerprint sets across observations.

If repeat observations are present but **stable** (all observations have identical exit codes and identical normalized fingerprint sets on both sides), skip this step and continue to step 3.

### Step 3: GO

**Precondition**: steps 1–2 did not match.
**Condition**: `candidate_exit_code == 0`.

The candidate passes. This is `GO` regardless of whether the base passes or fails:
- **Base passes, candidate passes**: clean green.
- **Base fails, candidate passes**: candidate removed baseline failures. `fingerprint_comparison.base_only` records the removed debt.

### Step 4: REGRESSION

**Precondition**: steps 1–3 did not match (therefore `candidate_exit_code != 0`).
**Condition**: `base_exit_code == 0`.

Green baseline broken by a failing candidate.

### Step 5: PARTIAL_REGRESSION

**Precondition**: steps 1–4 did not match (therefore both exit codes are non-zero).
**Condition**: normalized `candidate_only` fingerprint set is non-empty.

Baseline already broken; candidate introduces new failures (even if it also removed some baseline failures).

### Step 6: BASELINE_BROKEN

**Precondition**: steps 1–5 did not match (therefore both exit codes are non-zero, `candidate_only` is empty).
**Condition**: always matches at this point.

Baseline broken; candidate introduces no new failures. Sub-cases:
- **Identical failures**: `shared` equals the base set. Debt unchanged.
- **Candidate removes some failures**: `base_only` is non-empty, `shared` is smaller. Candidate improved but did not clear all debt.
- **Candidate removes all failures but still fails**: impossible under this step because `candidate_exit_code != 0` and `candidate_only` is empty means the candidate must share fingerprints with the base.

### Exhaustiveness proof

Steps 1–6 cover every combination of:
- Preflight valid/invalid (step 1 vs 2–6).
- Repeat observations present/absent and stable/unstable (step 2 vs 3–6).
- Candidate pass/fail (step 3 vs 4–6).
- Base pass/fail (step 4 vs 5–6).
- Candidate-only fingerprints empty/non-empty (step 5 vs 6).

No valid input that passes step 1 can fall through without matching.

## Fingerprint comparison rules

- Fingerprints are compared as **normalized sets**. Ordering and duplicate fingerprints must not change classification.
- `base_only` = fingerprints in `base` but not in `candidate`.
- `candidate_only` = fingerprints in `candidate` but not in `base`.
- `shared` = fingerprints in both.
- A side is green **only** when its exit code is `0` **and** its fingerprint list is explicitly present and empty (`[]`).

## Repeat observation binding

Each entry in `repeat_observations` must:
- Inherit the same `task_id`, `profile`, `selector`, `base_revision`, `candidate_revision`, and `producer_id` as the top-level object.
- Contain complete, consistent `base_exit_code`, `candidate_exit_code`, `base_fingerprints`, and `candidate_fingerprints` fields.
- Pass the same exit-code/fingerprint consistency preflight (rules E1–E7) as the top-level snapshot.

### Top-level snapshot vs repeats

When `repeat_observations` is present, the top-level `base_exit_code`, `candidate_exit_code`, and `failure_fingerprints` must be **explicitly bound** to one identified observation:

1. The H4 object must include `representative_run_number` (integer, 1-based) identifying which repeat observation the top-level snapshot corresponds to.
2. After normalization, the top-level exit codes and fingerprint sets must **exactly match** the identified observation's values.
3. If `representative_run_number` is missing, does not identify a valid observation, or the top-level values do not match the identified observation after normalization → step 1 `INCONCLUSIVE`.
4. After that binding passes, variation across the complete repeat set → step 2 `FLAKY_SUSPECT`.
5. After that binding passes, stable repeats continue through steps 3–6 using the agreed values.

If no `repeat_observations` is present, classification proceeds through steps 3–6 using the top-level snapshot alone.

Contradictory top-level evidence must never be accepted by merely recording a conflict note. `binding_metadata.conflict_note` is **not** a valid alternative to binding validation.

### Stable repeats

If `repeat_observations` has ≥ 2 valid observations and **all observations agree** on exit codes and normalized fingerprint sets for both sides:
- The observations are stable.
- Skip step 2 (not flaky).
- Continue to step 3 using the agreed-upon values.

## Edge case resolution

| # | Case | Resolution |
|---|---|---|
| 1 | Base fails, candidate passes | Step 3: `GO`. `base_only > 0` records removed debt. |
| 2 | Base and candidate fail with identical fingerprints | Step 6: `BASELINE_BROKEN`. Debt unchanged. |
| 3 | Base and candidate fail; candidate removes some baseline failures and adds new ones | Step 5: `PARTIAL_REGRESSION`. `candidate_only > 0`. |
| 4 | Base passes, candidate fails with multiple fingerprints | Step 4: `REGRESSION`. |
| 5a | Both exit 0, fingerprints differ after normalization | Step 3: `GO`. Both pass; fingerprint differences are irrelevant when both sides are green. |
| 5b | Both non-zero, `candidate_only > 0` | Step 5: `PARTIAL_REGRESSION`. Candidate introduces new failures. |
| 5c | Both non-zero, `candidate_only == 0`, `base_only > 0` (strict subset) | Step 6: `BASELINE_BROKEN`. Candidate shares a subset of base failures, no new failures. |
| 6 | Profile, selector, task, revision, or producer binding mismatch | Step 1: `INCONCLUSIVE`. |
| 7 | One side times out or has missing evidence | Step 1: `INCONCLUSIVE` (E6, E7). |
| 8 | Repeated runs alternate on only one side | Step 2: `FLAKY_SUSPECT`. |
| 9 | Both sides are unstable | Step 2: `FLAKY_SUSPECT`. |
| 10 | Fingerprint order differs but normalized sets are equal | Order-invariant; classification unchanged. |
| 11 | Non-zero exit code, empty fingerprint list | Step 1: `INCONCLUSIVE` (E3). |
| 12 | Base fails, candidate fails, candidate fingerprints are strict subset of base | Step 6: `BASELINE_BROKEN` (`candidate_only` empty, `base_only` non-empty). |
| 13 | Stable repeats, both sides agree | Skip step 2; continue to steps 3–6. |
| 14 | Revision binding absent or base == candidate | Step 1: `INCONCLUSIVE`. |

## Boundary rules

- `differential_status: GO` is a **probe-evidence classification only**. It must not self-approve a worker report or replace the coordinator's 14-point rubric.
- `REGRESSION`, `PARTIAL_REGRESSION`, `BASELINE_BROKEN`, `FLAKY_SUSPECT`, and `INCONCLUSIVE` are **not task lifecycle enum values**.
- Do not overload H2 producer-internal `status: rejected` or H3 recommendation values.
- Workers must not set `differential_status`; it is produced by trusted evidence analysis, not by worker self-assessment.

## Classification matrix

Every row is mechanically derivable from the ordered decision procedure. The "Step" column indicates which step fires.

| # | Base exit | Candidate exit | Base FP | Candidate FP | Repeat? | Step | Status |
|---|---|---|---|---|---|---|---|
| 1 | 0 | 0 | [] | [] | — | 3 | `GO` |
| 2 | 0 | 0 | [] | [] | stable | 3 | `GO` |
| 3 | 0 | 0 | [] | [] | unstable | 2 | `FLAKY_SUSPECT` |
| 4 | 0 | 1 | [] | [x] | — | 4 | `REGRESSION` |
| 5 | 0 | 1 | [] | [x] | stable | 4 | `REGRESSION` |
| 6 | 0 | 1 | [] | [x] | unstable | 2 | `FLAKY_SUSPECT` |
| 7 | 1 | 0 | [x] | [] | — | 3 | `GO` |
| 8 | 1 | 0 | [x] | [] | stable | 3 | `GO` |
| 9 | 1 | 0 | [x] | [] | unstable | 2 | `FLAKY_SUSPECT` |
| 10 | 1 | 1 | [x] | [x] (same) | — | 6 | `BASELINE_BROKEN` |
| 11 | 1 | 1 | [x] | [y] (candidate_only > 0) | — | 5 | `PARTIAL_REGRESSION` |
| 12 | 1 | 1 | [x] | [x,y] (shared + new) | — | 5 | `PARTIAL_REGRESSION` |
| 13 | 1 | 1 | [x,y] | [x] (base_only > 0) | — | 6 | `BASELINE_BROKEN` |
| 14 | 1 | 1 | [x,y] | [x] (strict subset) | — | 6 | `BASELINE_BROKEN` |
| 15 | 1 | 0 | [x,y] | [] | — | 3 | `GO` (candidate cleared all debt) |
| 16 | ? | ? | — | — | — | 1 | `INCONCLUSIVE` (binding mismatch) |
| 17 | ? | ? | — | — | — | 1 | `INCONCLUSIVE` (missing fields) |
| 18 | ? | ? | — | — | — | 1 | `INCONCLUSIVE` (untrusted producer) |
| 19 | 1 | 1 | — | [] | — | 1 | `INCONCLUSIVE` (E3: non-zero + empty FP) |
| 20 | 0 | 1 | [] | — | — | 1 | `INCONCLUSIVE` (E4: non-zero + missing FP key) |
| 21 | 0 | 0 | — | [] | — | 1 | `INCONCLUSIVE` (E5: exit 0 + missing FP key) |

## Evidence Ladder Relationship (J2)

The evidence ladder (`references/evidence-ladder-v0.1.md`) defines three evidence strength levels — **static recompute** (level 1), **offline regeneration** (level 2), and **runtime smoke** (level 3) — and maps each task shape to a minimum required level.

H4 `differential_status` operates at **level 2 or level 3** depending on the trusted producer:

| H4 producer type | Evidence ladder level |
|---|---|
| Unit test / fixture runner | Level 2 (offline regeneration) |
| Integration / smoke test runner | Level 3 (runtime smoke) |
| Build / lint / static analysis | Level 1 (static recompute) — H4 classification is still valid but the evidence level may be insufficient for the task shape |

Key interactions:

- **H4 `GO` + level-2 evidence** is sufficient for bug fixes and configuration changes, but insufficient for semantic behavior changes or cross-module value-flow changes (which require level 3).
- **H4 `GO` + level-3 evidence** satisfies the evidence ladder for all task shapes.
- **H4 `REGRESSION` / `PARTIAL_REGRESSION`** is always actionable regardless of evidence level — it identifies a problem even if the root cause needs higher-level evidence to confirm.
- **H4 `BASELINE_BROKEN`** identifies historical debt; the evidence ladder determines whether the candidate change is adequately verified given that debt.
- **H4 `FLAKY_SUSPECT`** means evidence is unreliable; the coordinator must request stable evidence at the required level before closing.

The evidence ladder is an **additional hard gate** on top of H4. H4 classification and evidence-ladder sufficiency are independent checks — both must pass for coordinator `GO`.

## Backward compatibility

- Existing `agent-file-coordination/*` schema identifiers remain unchanged.
- `schema_version: 0.1.0` remains valid.
- Unknown frontmatter keys are ignored by `validate-agent-inbox.py`.
- Task and report files without `differential_status` are still fully valid.

## Non-goals

- This document does not implement probes, runners, Docker, daemons, or adapters.
- This document does not change task lifecycle states or coordinator verdict logic.
- This document does not add mandatory runtime behavior.
