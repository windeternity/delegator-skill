# Evidence Ladder and Hypothesis Labeling v0.1

This document is an **extension note** for the `agent-file-coordination` protocol. It builds on `references/differential-validation-v0.1.md` (H4) and `references/decision-rubric.md`. It does not replace existing schemas or change schema identifiers. All concepts defined here are **protocol guidance** — enforceable by the coordinator at review time.

## Purpose

Worker-predicted impact tables and root-cause attributions repeatedly read as facts but proved wrong in field use (a predicted 7-case behavior change measured 0 at runtime; a smoke agent's root cause was mis-attributed and nearly drove a wrong fix). Semantic changes were closed on static evidence; cross-module value-flow changes looped through three repair rounds because nobody mapped the full set/override chain.

This document defines:
1. A three-level evidence ladder that constrains what evidence is sufficient to close different task types.
2. Mandatory labeling conventions for predictions and root-cause claims.
3. Task-shape-specific requirements that prevent false-confidence patterns.

## Evidence Ladder

Evidence strength is **ordered**. Higher levels subsume lower levels; lower levels alone are insufficient for tasks that require higher levels.

| Level | Name | Description | Examples |
|---|---|---|---|
| 1 | **Static recompute** | Evidence derived from reading source, tracing control flow, or computing expected values by hand. No execution. | Code review, static analysis output, manual value tracing, schema lint. |
| 2 | **Offline regeneration** | Evidence from executing code or scripts in a controlled, non-production environment. Output is captured and compared against expected values. | Unit test output, fixture runs, build verification, `audit-docs.py` output, validator runs. |
| 3 | **Runtime smoke** | Evidence from executing the actual pipeline or integration path end-to-end, observing real behavior at the boundary where the change matters. | Integration test that exercises the full value flow, smoke test of the changed behavior, production-replay validation, browser test of the affected UI flow. |

### Evidence-level sufficiency by task shape

| Task shape | Minimum evidence level to `CLOSED_*` | Rationale |
|---|---|---|
| Documentation-only (no behavior change) | Level 1 (static) | No behavior to verify at runtime. |
| Lint, formatting, naming | Level 1 (static) | No semantic behavior change. |
| Configuration or setting change with observable effect | Level 2 (offline) | Must verify the setting takes effect. |
| Bug fix (single-module, value unchanged across boundary) | Level 2 (offline) | Unit/fixture test confirms the fix. |
| Semantic behavior change (value or control flow changes at a boundary) | Level 3 (runtime) | Static and offline evidence cannot confirm boundary behavior. |
| Cross-module value-flow change | Level 3 (runtime) | See § Value-flow task requirements. |
| State-machine or enum change | Level 3 (runtime) | See § State-machine task requirements. |

**Rule**: A task whose evidence level is below the minimum for its shape cannot receive coordinator `GO`. Use `PARTIAL` with a request for higher-level evidence, or `RED` if the gap is fundamental.

### Evidence level vs. verdict authority

Evidence strength informs the coordinator's verdict but does **not** replace it. A task can have runtime-level evidence (level 3) and still receive `RED` for scope violations, safety issues, or semantic contradictions. The 14-point rubric in `references/decision-rubric.md` remains the final authority. Evidence ladder compliance is an additional hard gate, not a substitute.

## Hypothesis Labeling

### Predicted-impact tables

When a worker report includes a predicted-impact table (e.g., "this change affects cases 1-7" or "expected behavior: X"), the table **must** carry a `hypothesis` label. Predictions are not facts until verified by evidence at the required level.

Format:

```markdown
### Predicted Impact (hypothesis)

| Case | Predicted behavior | Evidence level | Verified? |
|---|---|---|---|
| case-1 | Value passes through unchanged | static | yes (line 42) |
| case-2 | Value is overridden at boundary | offline | no |
```

Rules:
- Every predicted-impact table must include the `(hypothesis)` suffix in its heading.
- Each row must declare which evidence level supports the prediction.
- "Verified?" column must be `yes` (with a reference) or `no`. Do not leave blank.
- When all rows are verified at the required evidence level, the coordinator may remove the `hypothesis` label at verdict time by noting it in the verdict's `evidence_checked` field.

### Root-cause fields

When a report attributes a root cause, the attribution **must** be labeled:

- `confirmed` — backed by code-level evidence (a specific line, a specific state transition, a specific value path). Must reference a file path and line number or a reproducible test case.
- `suspected` — based on pattern matching, experience, or partial evidence. Not yet verified at the required evidence level.

Format:

```markdown
### Root Cause
- **Label**: confirmed
- **Location**: `scripts/validate.py:142` — off-by-one in fingerprint set comparison
- **Evidence**: unit test `test_fingerprint_set_boundary` passes after fix, failed before
```

```markdown
### Root Cause
- **Label**: suspected
- **Reasoning**: The error only appears when the value flows through module B after module A changes; likely a stale cache in B's transform step.
- **Evidence needed**: runtime smoke test tracing the value through A → B
```

Rules:
- `confirmed` requires a file:line reference or a reproducible test case.
- `suspected` requires a reasoning line and an explicit "Evidence needed" line stating what would raise it to `confirmed`.
- A root cause labeled `suspected` is insufficient to close a semantic behavior change task. The coordinator must request the evidence needed to confirm or refute.

## Value-Flow Task Requirements

A task that changes how a value flows across modules (set/override chains, transform pipelines, configuration cascades, inheritance hierarchies) has specific requirements that prevent the false-confidence pattern observed in field use: unit-level matrix tests alone passed while the full pipeline silently broke.

### Pre-implementation inventory

Before implementation begins, the task (or an audit predecessor) must deliver a **complete set/override-point inventory**:

```markdown
### Value-Flow Inventory

| Point | Module | Operation | Line | Upstream source |
|---|---|---|---|---|
| set-default | module-a | `config.set('key', default)` | a.py:42 | — |
| override-1 | module-b | `config.set('key', override)` | b.py:18 | set-default |
| consume | module-c | `config.get('key')` | c.py:91 | override-1 |
```

Rules:
- Every set, override, and consume point in the affected value chain must be listed.
- "Upstream source" traces where the value came from.
- The inventory must be complete before implementation begins (or delivered as part of an audit task).

### Acceptance criteria

Value-flow tasks must include **one full-pipeline integration test** in acceptance criteria. Unit-level matrix tests alone are a documented false-confidence pattern for this task shape.

Format:

```markdown
## Acceptance Criteria
- Complete set/override-point inventory (see above)
- One full-pipeline integration test: `test_full_value_flow_<scenario>`
- All existing unit tests pass
```

## State-Machine Task Requirements

Tasks that change state machines, enumerations, or status taxonomies must:

1. **Enumerate all states first.** Before implementation, list every state (or enum value, or status) in the affected machine, including terminal, error, and transitional states.
2. **Map transitions.** For each state, list valid next-states and the trigger/condition.
3. **Verify exhaustiveness.** Confirm that no valid input combination is unmapped.

For **fix tasks** (bug fixes in state-machine logic), add a **re-verify upstream attribution** step: confirm that the reported symptom actually originates in the fixed state transition, not in an upstream transition that feeds it.

## Audit-Task Requirements

Audit tasks (tasks whose purpose is to survey, inventory, or assess) must include in acceptance criteria:

> Produce a directly executable minimal-slice spec that an implementation task can reference verbatim.

This means the audit output must be specific enough that an implementation task can copy the relevant section as its acceptance criteria without re-interpretation.

## Coordinator Review Guidance

When reviewing a report, the coordinator should:

1. **Check evidence level sufficiency.** Does the task shape's minimum evidence level match the evidence actually provided?
2. **Check hypothesis labeling.** Are predicted-impact tables labeled? Are root causes labeled `confirmed` or `suspected`?
3. **Check value-flow inventory.** For cross-module value-flow tasks, is the set/override inventory present and complete?
4. **Check state-machine enumeration.** For state-machine tasks, are all states listed?
5. **Escalate suspected root causes.** If a root cause is `suspected` and the task is a semantic behavior change, request the evidence needed before issuing `GO`.

These checks are **hard gates** — they apply even when the 14-point score is 14/14. A task can score perfectly on scope, validation, and safety while still having insufficient evidence for its task shape.

## Relationship to Existing References

| Existing reference | J2 relationship |
|---|---|
| `references/decision-rubric.md` | Evidence ladder adds a hard gate beyond the 14-point score. The rubric's "Evidence quality" dimension measures completeness; the ladder measures fitness-for-task-shape. |
| `references/differential-validation-v0.1.md` | H4 `GO` status (candidate passes) is level-2/3 evidence. H4 `BASELINE_BROKEN` or `REGRESSION` informs but does not replace the evidence ladder — a task can have H4 `GO` and still lack level-3 evidence for a semantic change. |
| `references/evidence-expansion-v0.1.md` | H3 expansion can retrieve evidence to satisfy a higher ladder level, but expansion alone does not change the evidence level — the expanded content must be from a higher-level source. |
| `references/protocol-design-review-checklist.md` | Checklist item 9 (cross-section consistency) should include evidence-level sufficiency checks. |

## Backward Compatibility

- Existing `agent-file-coordination/*` schema identifiers remain unchanged.
- `schema_version: 0.1.0` remains valid.
- No new frontmatter fields are required. Evidence ladder compliance is enforced at review time, not at schema level.
- Task and report files without evidence ladder fields are still structurally valid; the coordinator enforces compliance during review.

## Non-goals

- This document does not implement probes, runners, or runtime validators.
- This document does not change task lifecycle states or schema identifiers.
- This document does not add mandatory frontmatter fields.
- This document does not replace the 14-point rubric or the coordinator's final verdict authority.
