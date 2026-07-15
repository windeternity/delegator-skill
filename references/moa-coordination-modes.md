# MOA Coordination Modes

Status: active guidance. These modes are optional metadata for `FULL` tasks.
They do not replace the binding `DIRECT / LITE / FULL / SPLIT` route decision.

## Field

Use `coordination_mode` when a `FULL` task needs to distinguish ordinary
delegation from MOA coordination:

```yaml
coordination_mode: delegate_full | moa_review | moa_design | moa_patch | moa_synthesis
comparison_group: <stable-id>
```

`comparison_group` ties candidate tasks, reports, and synthesis together.

## Modes

| Mode | Purpose | Source edits |
| --- | --- | --- |
| `delegate_full` | Different workers own different workstreams | Allowed only inside assigned locks |
| `moa_review` | Multiple workers independently review the same decision surface | Default no |
| `moa_design` | Multiple workers propose alternative designs | No |
| `moa_patch` | Multiple workers produce isolated candidate patches | Dedicated worktrees only |
| `moa_synthesis` | Compare candidate reports and recommend a coordinator decision | No |

## Candidate Task Metadata

```yaml
coordination_mode: moa_review
comparison_group: moa-routing-policy-001
moa:
  layer: candidate
  decision_surface: routing policy MOA gate
  previous_outputs_visible: no
  synthesis_expected: yes
source_artifacts:
  - references/delegation-routing-v1.md
  - docs/WHEN_TO_USE_AFC.md
```

Candidate tasks should keep `previous_outputs_visible: no` unless the purpose
is explicit peer critique. Independence is the point.

## Synthesis Task Metadata

```yaml
coordination_mode: moa_synthesis
comparison_group: moa-routing-policy-001
moa:
  layer: synthesis
  decision_surface: routing policy MOA gate
  inputs:
    - examples/moa-review-demo/report-ReviewerA-routing-policy.md
    - examples/moa-review-demo/report-ReviewerB-routing-policy.md
```

The synthesis pass compares reports; it does not inherit worker authority.
Final `GO / PARTIAL / RED` still belongs to the coordinator verdict.

## Challenge Review Preset

Challenge (adversarial) review is a **task shape**, not a new mode or field. It
reuses `moa_review` (or a single `delegate_full` reviewer task) with a purpose
that pressure-tests the work instead of just hunting defects.

Use it when the coordinator needs an independent reviewer to challenge design,
tradeoffs, assumptions, rollback, race conditions, security/privacy, and whether
a simpler approach is safer. Do not use it for tiny direct edits or purely
mechanical changes.

Drop this into the candidate task's purpose (no schema change):

```text
Purpose:
Run an adversarial review of the current implementation. Challenge the design,
tradeoffs, assumptions, rollback path, race conditions, reliability risks, and
whether a simpler approach would be safer.

Non-goals:
Do not patch code. Do not approve final GO/PARTIAL/RED. Do not expand scope. Do
not request permission escalation.

Evidence to report:
Concrete file refs, risk reasoning, likely false positives, and recommended
follow-up. Worker agreement is not authority.
```

The report uses the normal task/report schema and remains evidence only. Final
`GO / PARTIAL / RED` still belongs to the coordinator verdict.

## Rules

- Do not use MOA labels for ordinary split implementation.
- Do not let candidate workers see each other's outputs by default.
- Do not count votes. Rank evidence.
- Do not edit source in `moa_review`, `moa_design`, or `moa_synthesis`.
- Use dedicated worktrees for `moa_patch`.
- Keep acceptance criteria short enough for one report and one synthesis pass.

