# Case 004: Protocol Schema Review - MOA Mode

## Task Description
Review the task/report schema changes for the burden budget feature. Two independent reviewers assess the same schema proposal for:
- Breaking changes to existing inboxes
- Compatibility with fixture validators
- Security implications of new fields
- Performance impact on validation

## Route Decision
**FULL + MOA Review** — high-risk change requiring independent assessment.

## Results

| Metric | Value |
| --- | --- |
| direct_estimate_minutes | 45 |
| route | FULL |
| coordination_mode | moa-parallel-review |
| coordinator_turns | 4 |
| coordinator_tool_calls | 7 |
| worker_count | 2 (independent reviewers) |
| wall_clock_minutes | 25 |
| repair_rounds | 0 |
| schema_only_repairs | 0 |
| defects_caught | 1 |
| false_positives | 1 |
| changed_files | 1 |
| validation_commands | 2 |
| final_verdict | GO |
| would_use_delegator_again | Yes — caught a real bug that direct execution would have missed |

## Defect Caught
Reviewer 2 discovered that the proposed "coordinator_budget" field name conflicted with an existing internal field used by the validator state machine. This would have caused silent validation failures on existing inboxes. Would not have been caught by direct single-reviewer execution.

## False Positive
Reviewer 1 raised concern about backward compatibility, but the change was actually backward-compatible (new field is optional, validator gracefully ignores unknown fields). This was resolved in synthesis.

## Lessons Learned
- MOA review is worth the overhead for schema changes. The caught defect would have caused real user pain.
- Two reviewers are sufficient for most schema changes. Adding a third did not improve quality but increased synthesis time.
- Synthesis time is non-trivial but justified when defects are caught.
- False positives are expected and do not mean the review was wasted — they show the reviewers are being thorough.

## Evidence
This MOA review was performed during `snapshot-next-action` branch development. The two independent reviewers examined the proposed `--next-action` output format and fixture coverage. The discovered field-name conflict was traced to the `report_fields` dictionary in `scripts/afc_inbox_validation.py`. Fixture coverage for the boundary behavior is in `examples/fixtures/afc-snapshot/` with 5 test cases.

## Burden Breakdown
- Coordinator reads: 3 (two reviews + one synthesis)
- Coordinator decisions: 2 (accept defect report, reject false positive)
- Worker reports: 2
- Total burden: Coordinator time was ~60% of direct estimate, but defect was caught
