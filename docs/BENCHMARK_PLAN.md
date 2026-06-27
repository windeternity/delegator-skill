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

## Record Template

```yaml
benchmark_case:
  case_id:
  task_type:
  decision_surface:
  route:
  coordination_mode:
  direct_estimate_minutes:
  coordinator_input_tokens:
  coordinator_output_tokens:
  worker_total_tokens:
  synthesis_tokens:
  wall_clock_minutes:
  repair_rounds:
  defects_caught:
  defects_missed:
  false_positives:
  changed_files:
  validation_commands:
  final_verdict:
  confidence_before:
  confidence_after:
  notes:
```

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
