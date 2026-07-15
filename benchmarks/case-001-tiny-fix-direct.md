# Case 001: Tiny Fix - Typo Correction

## Task Description
Correct a 3-word typo in a README file. No semantic change, no code change.

## Route Decision
**DIRECT** — coordination overhead would exceed the value.

## Results

| Metric | Value |
| --- | --- |
| direct_estimate_minutes | 2 |
| route | DIRECT |
| coordination_mode | direct |
| coordinator_turns | 1 |
| coordinator_tool_calls | 1 (Edit) |
| worker_count | 0 |
| wall_clock_minutes | 1 |
| repair_rounds | 0 |
| schema_only_repairs | 0 |
| defects_caught | 0 |
| false_positives | 0 |
| changed_files | 1 |
| validation_commands | 0 |
| final_verdict | GO |
| would_use_delegator_again | No — task too small |

## Lessons Learned
- Tiny edits should always stay DIRECT. The routing gate already enforces this correctly.
- Even 30 seconds of coordinator routing decision time is 15% of total task time.
- Any coordination overhead would have been 5-10x the direct cost.

## Evidence
This is a reconstructed synthetic calibration case based on observed routing behavior, not a recorded coordination run. The direct timing estimate is based on accumulated observation of actual single-file typo fix runs. Routing behavior is validated by `examples/fixtures/afc-efficiency/run-tests.py`, especially the route truth table covering tiny tasks and DIRECT decisions.

## Burden Breakdown
- Coordinator reads: 1 (README to find typo)
- Coordinator decisions: 1 (accept change)
- Total burden: ~1 minute saved by staying direct
