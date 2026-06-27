# Protocol-Design Review Checklist

> Conditional on-demand reference. Use this checklist for protocol/schema/decision-table/permission-model/document-contract tasks. Do not use it for routine code tasks (implementation, bug fixes, non-protocol docs). The coordinator decides when to apply it, not the worker.

## When To Use

Apply when the task touches any of:
- schema or `schema_version` changes
- task/report/verdict frontmatter or lifecycle states
- permission scope, workspace mode, or coordinator authority definitions
- decision rubric, verdict mapping, or evidence trust levels
- protocol contracts across `SKILL.md`, `references/`, `templates/`, `docs/`, `examples/`, or `scripts/`
- fixture semantics that define pass/fail for protocol rules

Skip for: implementation-only tasks, non-protocol docs, routine bug fixes, script changes that don't change protocol semantics.

## Checklist

### 1. Authority and Ownership

- [ ] Every concept, file, and state has exactly one owner (coordinator, worker, script, or user).
- [ ] Workers do not grant themselves permission, coordinator authority, or final verdict power.
- [ ] Task-level permission scope is the effective permission — role authority narrows but never expands it.
- [ ] Prose descriptions of authority match the machine-readable `permission_scope` and `coordinator_authority` fields.

### 2. Effective Permission Intersection

- [ ] The effective permission is the intersection of `role` capability and task `permission_scope`.
- [ ] `coordinator_authority: yes` does not override a task scope that says `write_task_files: no`.
- [ ] `modify_source: yes` paired with `locked_files_or_areas` — the lock is narrower than the grant; verify the intersection is intentional.

### 3. Schema and Backward Compatibility

- [ ] `schema` identifiers are preserved unless an explicit `schema_version` bump is documented.
- [ ] New fields are additive; existing required fields are not removed or renamed without a migration path.
- [ ] Every fixture and template that uses the schema is updated consistently.

### 4. Upstream/Downstream Contract Mapping

- [ ] Every interface that produces data (task file, report, probe, script output) names its consumers.
- [ ] Every interface that consumes data (verdict, expansion request, status board) names its producers.
- [ ] Breaking a producer contract is treated as a downstream breaking change.

### 5. Ordered Decision Procedure

For any status, classification, or verdict taxonomy:
- [ ] The decision procedure is ordered (e.g., check A first, then B, then C).
- [ ] When two statuses could match the same evidence, the order resolves the conflict.
- [ ] The first-matching rule wins; fall-through is explicit.

### 6. Truth-Table Properties

- [ ] **Exhaustiveness**: every valid input combination maps to exactly one output.
- [ ] **Mutual exclusion**: no input combination maps to two different outputs.
- [ ] **Precedence**: when statuses could overlap, the ordering rule is stated.
- [ ] **Fail-closed invalid input**: unrecognized or contradictory input maps to an explicit sentinel (not a default pass).
- [ ] **Empty/null/zero cases**: explicitly classified, not silently treated as valid or green.

### 7. Fixture Coverage

- [ ] At least one **positive** fixture (should pass).
- [ ] At least one **negative** fixture per distinct failure mode (should fail).
- [ ] At least one **boundary** fixture (edge of a threshold, exactly-at-limit, empty input).
- [ ] At least one **contradiction** fixture where two rules could both claim the same input.
- [ ] Fixture metadata (filename, description, expected result) matches the fixture content.

### 8. Metadata / Prose / Example Consistency

- [ ] Every example in prose is also covered by a fixture or explicitly marked as illustrative.
- [ ] Metadata fields (e.g., `verdict`, `score`, `changed_files`) are consistent with the prose description.
- [ ] No claim in prose contradicts a machine-readable field in the same artifact.

### 9. Cross-Section Consistency

After all edits are complete, run targeted searches:
- [ ] Search for stale terminology (old names, removed states, deprecated fields) across all changed and related files.
- [ ] Search for contradictory rules (e.g., "must X" in one section and "must not X" in another).
- [ ] Search for orphan references (pointers to files that were moved, renamed, or deleted).
- [ ] Search for claims that validators, linters, or doc audits prove semantic correctness — they do not.

### 10. Changed-File Reporting

- [ ] Every file created, modified, or deleted is listed.
- [ ] No file outside the task's `permission_scope` and `locked_files_or_areas` is changed.
- [ ] `git status --short` output is included in the report or evidence.

## Validation Evidence Required

For protocol-design tasks, the worker must report:
- [ ] Completed checklist with checkmarks and notes for any unchecked items.
- [ ] Results of targeted cross-section searches (search terms and match counts).
- [ ] Validation command results (`validate-agent-inbox.py`, `audit-docs.py`, `check-public-safety.py`).
- [ ] `git diff --check` and `git status --short` output.
