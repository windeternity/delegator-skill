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

## Coordinator Burden Budget

Every coordination mode has a hot-path budget. The project will not add concepts, fields, or required steps that expand these budgets.

| Route | Budget |
| --- | --- |
| **DIRECT** | 1 route decision, no roster hydration, no task/report artifacts |
| **LITE** | 1 route decision, 1 compact handoff, 1 worker result check, no inbox artifact |
| **FULL** | 1 route decision, 1 roster confirmation per session, 1 dispatch batch, 1 selected-batch intake, **1 consolidated repair request maximum before escalation**, 1 integrated quality gate, 1 final verdict |
| **MOA** | 2-3 independent candidate reports maximum by default, synthesis compares evidence not votes, **no schema-only repair round** if the report helper is available |

Schema-only repair rounds (worker reports fail validation for purely structural reasons, not semantic reasons) are explicitly tracked as a protocol failure mode. They should not require coordinator manual intervention.

## Burden Impact Checklist

For any future protocol change, answer these questions:

1. **Adds/removes coordinator reads?**
2. **Adds/removes worker repair rounds?**
3. **Adds/removes required fields?**
4. **Changes hot-path commands?**
5. **Measured or expected break-even?**

If the change expands the burden budget without removing something else, it needs strong evidence and explicit approval.

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

## Anti-Weight Governance Rules

Every change to the protocol must pass this burden review:

1. **No new required task/report field** unless it replaces at least one existing field OR enables a validator that removes a coordinator manual check. If the field is optional only and non-breaking, it does not need to replace anything but must still justify the burden cost.

2. **No new user-facing mode** unless an existing mode cannot express the behavior safely. Every new mode must document what existing mode it deprecates or what coordinator decision it removes.

3. **No new hot-path document.** New documentation must be reference-only or replace older documentation. The documentation tree should shrink or stabilize, not grow indefinitely with every release.

4. **No new mandatory command** unless it combines two or more existing commands OR removes a manual coordinator decision. Helper scripts must reduce total coordinator work, not add to it.

5. **No expansion of root SKILL.md** unless equal or larger content moves out of the hot path. The SKILL.md is the coordinator's primary entry point — it should be compact and stable.

6. **No CAL-3 promotion.** CAL-3 may be documented and used but must not be positioned as the default recommendation until evidence shows it reduces coordinator burden without increasing safety incidents.

7. **No broad public claim** without a benchmark or case record. All claims about Delegator's value must be grounded in real use data, not hypothetical benefits.

8. **No worker authority expansion** without a protocol design review. Workers must not gain the ability to modify coordination state, task files, status boards, or verdict mechanisms without explicit review of the burden and safety implications.

### Burden Impact Statement

Any PR that modifies the protocol must answer:
- Adds/removes coordinator reads?
- Adds/removes worker repair rounds?
- Adds/removes required fields?
- Changes hot-path commands?
- Measured or expected break-even?

