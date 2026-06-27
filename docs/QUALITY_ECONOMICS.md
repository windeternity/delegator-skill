# Quality Economics

Delegator should optimize quality-adjusted coordination return, not raw worker
count and not token savings alone.

## Principle

Small tasks should stay direct. Substantive semantic tasks may justify higher
total token cost if independent evidence catches errors or raises confidence
enough to matter.

The useful question is:

```text
Did the coordination cost buy better evidence or lower coordinator burden than
direct execution would have?
```

## Quality-Adjusted Coordination ROI

Use this as a review frame, not as a precise accounting formula:

```text
quality_adjusted_roi =
  defects_avoided_value
  + semantic_confidence_gain
  + coordinator_tokens_saved
  + coordinator_attention_saved
  - worker_token_cost
  - synthesis_token_cost
  - latency_cost
  - repair_round_cost
  - false_positive_cost
  - coordination_overhead
```

## What To Record

For dogfood runs and benchmark cases, record enough to compare direct,
delegated, and MOA paths:

- task type and decision surface;
- direct estimate in minutes;
- route decision and `coordination_mode`;
- worker count and model diversity basis;
- coordinator input and output tokens when available;
- worker and synthesis tokens when available;
- wall-clock minutes;
- repair rounds;
- defects caught;
- false positives;
- validation commands;
- final coordinator verdict and confidence.

## Success And Failure

MOA succeeds when it exposes a real contradiction, catches a defect, improves a
decision, or makes the coordinator's final verdict more evidence-backed.

MOA fails when it produces several low-quality reports that the coordinator must
debug, when synthesis becomes more expensive than direct work, or when worker
agreement is treated as authority.

Delegation succeeds when bounded workers reduce wall-clock or coordinator
execution load without creating extra repair rounds.

Delegation fails when task setup, report intake, and integration cost exceed
the direct path.

## Guardrails

- Do not use MOA for tiny non-semantic edits.
- Do not treat majority agreement as proof.
- Do not count worker self-verdicts as final authority.
- Do not hide coordination cost by omitting synthesis effort.
- Do not publish model rankings from local dogfood data.

