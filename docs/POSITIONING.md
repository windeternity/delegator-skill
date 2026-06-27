# Positioning

Delegator is a local-file MOA coordination protocol for coding agents:
independent evidence in, coordinator verdict out.

## North Star

Delegator should be understood as a narrow coordination layer, not a general
agent runtime. Its value is to turn multiple model or agent outputs into bounded
task files, reports, evidence references, and final coordinator verdicts.

The product promise:

```text
Use multiple agents for judgment where they help, not everywhere.
Keep evidence in files.
Keep authority with the coordinator.
```

## What It Solves

Delegator is for cases where direct execution is too narrow, too expensive, or
too exposed to one model's blind spots. The user needs independent candidate
judgment, bounded worker permissions, auditable evidence, and one final
coordinator decision.

The core job is not "send tasks to agents". The core job is:

- define who may do what;
- capture what evidence they produced;
- preserve the permission and file boundaries;
- compare independent outputs when MOA is useful;
- keep `GO / PARTIAL / RED` authority with the coordinator.

## Boundaries

Delegator should not become:

- a full agent operating system;
- a worker execution runtime;
- an OpenSpec replacement;
- a model benchmark or leaderboard;
- a cloud dashboard;
- an auto-commit, auto-push, auto-merge, or deployment tool.

Those can exist around the protocol later, but they are not the core.

## Relationship To Other Tools

| Tool family | Owns | Delegator relationship |
| --- | --- | --- |
| Spec systems | Requirements, designs, task plans | Upstream source artifacts |
| Agent methods and skills | How one agent plans, tests, and reviews | Task quality discipline |
| Agent runtimes | Process launch, tool hooks, scheduling | Optional outer layer |
| Delegator | Assignment, report, evidence, verdict boundaries | Core protocol |

Delegator can reference upstream specs and external runtime outputs, but it
does not need to own them.

## Success Shape

A successful Delegator workflow does not prove that more agents are always
better. It proves that, for a specific decision surface, the added coordination
cost bought one or more of:

- stronger semantic confidence;
- a defect or contradiction caught by independent review;
- lower high-trust coordinator execution load;
- cleaner recovery from interruption;
- a better audit trail for the final verdict.

