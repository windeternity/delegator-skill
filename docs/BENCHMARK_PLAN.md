# Benchmark Plan

This plan records how to compare direct execution, ordinary delegation, and
MOA coordination. It is for product evidence, not for public model rankings.

## Comparison Groups

Every benchmark case should define the same task for up to three paths:

| Path | Description |
| --- | --- |
| `DIRECT` | Coordinator performs the work directly |
| `FULL` + `delegate_full` | Workers split independent workstreams |
| `AFC_MOA` | Workers independently review, design, or patch the same decision surface, then synthesis compares evidence |

Not every case needs all three paths. Tiny tasks should mainly prove that the
router keeps them direct.

## Case Types

| Case | Expected useful route | What to observe |
| --- | --- | --- |
| Tiny one-file fix | `DIRECT` | Coordination should be rejected |
| Medium semantic review | `AFC_MOA` | Independent findings and false positives |
| Protocol or schema change | `AFC_MOA` plus synthesis | Contract contradictions and validation gaps |
| Long multi-module implementation | `FULL` + `delegate_full` | Wall-clock reduction and integration cost |
| High-risk candidate patch | `AFC_MOA` | Whether comparison avoids a bad patch |

## Burden Metrics To Record

Every benchmark case tracks coordinator overhead alongside quality outcomes:

| Metric | Definition |
| --- | --- |
| `coordinator_turns` | Number of coordinator LLM turns consumed |
| `coordinator_tool_calls` | Number of tool calls the coordinator made |
| `repair_rounds` | Worker correction cycles triggered by coordinator |
| `schema_only_repairs` | Count of repair rounds for purely structural reasons (missing fields, formatting, etc.) |
| `coordinator_reads` | Files the coordinator had to read to understand the state |

Schema-only repairs are explicitly called out because they indicate protocol friction, not worker competence.

## Record Template

```yaml
benchmark_case:
  case_id:
  task_type:
  decision_surface:
  route:
  coordination_mode:
  direct_estimate_minutes:
  coordinator_turns:
  coordinator_tool_calls:
  coordinator_input_tokens:
  coordinator_output_tokens:
  worker_total_tokens:
  synthesis_tokens:
  wall_clock_minutes:
  repair_rounds:
  schema_only_repairs:
  defects_caught:
  defects_missed:
  false_positives:
  changed_files:
  validation_commands:
  final_verdict:
  would_use_delegator_again: yes/no/conditional
  confidence_before:
  confidence_after:
  notes:
```

## Completed Cases

Real benchmark evidence from actual use:

| Case | Summary | Key Finding |
| --- | --- | --- |
| [case-001](../benchmarks/case-001-tiny-fix-direct.md) | Tiny typo fix — DIRECT route | Direct execution is ~2x faster than any coordination overhead |
| [case-002](../benchmarks/case-002-docs-review-lite.md) | Documentation review — LITE route | LITE mode works well for single-worker low-risk tasks |
| [case-003](../benchmarks/case-003-multi-worker-optimization.md) | Burden optimization program — FULL route | FULL mode cuts wall-clock time by 50% for parallel work |
| [case-004](../benchmarks/case-004-moa-review-bug-catch.md) | Schema review — MOA route | MOA caught a real backward-compatibility bug that direct review missed |
| [case-005](../benchmarks/case-005-delegation-loss.md) | Tightly-coupled refactoring — Delegation Loss | Force-partitioning tightly-coupled work produces net loss |
| [case-006](../benchmarks/case-006-cal-boundary.md) | CAL-2 to CAL-3 transition — Mixed Mode | CAL boundary crossing works correctly with probe verification |

Full case details: [benchmarks/README.md](../benchmarks/README.md)

## Acceptance Signals

AFC does not need to win every case. A healthy benchmark set should show:

- tiny tasks route direct;
- MOA finds decision-relevant issues in semantic or protocol reviews;
- delegation helps when workstreams are genuinely independent;
- synthesis cost stays bounded and evidence-focused;
- false positives are visible and do not overwhelm the coordinator.

## Reporting Rule

Benchmark notes may mention the project-local roster and observed outcomes, but
must not present unstable model rankings as durable truth. Keep model facts in
the project-local roster and current evidence, not in reusable protocol claims.
