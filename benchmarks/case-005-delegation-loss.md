# Case 005: Tightly-Coupled Refactoring - Delegation Loss

## Task Description
Refactor the validation command flow across 3 tightly-coupled Python modules to support a new cross-feature validation gate. Files share data structures and require coordinated changes across all three simultaneously.

## Route Decision
**Attempted FULL — forced partitioning produced high integration overhead.**

## Results

| Metric | Value |
| --- | --- |
| direct_estimate_minutes | 60 |
| route | FULL (attempted) |
| coordination_mode | multi-parallel-worker |
| coordinator_turns | 12 |
| coordinator_tool_calls | 28 |
| worker_count | 3 (one per module) |
| wall_clock_minutes | 90 |
| repair_rounds | 4 |
| schema_only_repairs | 1 |
| defects_caught | 0 |
| false_positives | 2 |
| changed_files | 3 |
| validation_commands | 6 |
| final_verdict | GO (but net loss) |
| would_use_delegator_again | No — tightly-coupled cross-module refactoring should stay direct |

## Lessons Learned
- **Force-partitioning is an antipattern.** When files are tightly coupled, splitting across workers creates more integration work than it saves.
- High repair round count (4) is a coordination failure signal. When repair rounds exceed worker count, delegation probably shouldn't have been used.
- One schema-only repair was needed because workers independently chose different field name conventions.
- Coordinator time was 150% of the direct estimate. Wall clock was also 50% worse than direct.
- The task would have been better done in a single session without handoff boundaries.

## When to Recognize This Pattern
- Multiple files sharing data structures or interfaces
- Any task where "worker A needs to see what worker B produces" to finish
- Refactoring that touches the API boundary between modules
- Tasks requiring consensus on naming or structure across files

## Evidence
This is a reconstructed synthetic calibration case based on observed anti-patterns seen during Delegator's own development. The metrics are typical of force-partitioned tightly-coupled work. The `examples/fixtures/afc-efficiency/run-tests.py` fixtures test for excessive repair-round detection.

## Burden Breakdown
- Coordinator reads: 18 (task files, worker reports, integration repair, final validation)
- Coordinator decisions: 8 (including arbitration between conflicting worker choices)
- Worker reports: 6 (3 initial + 3 repair rounds)
- Total burden: Net loss — coordinator time increased 2.5x vs direct execution
