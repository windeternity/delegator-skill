# When To Use AFC

Use AFC only when coordination changes the outcome enough to pay for its
startup cost. The default for small, clear work is direct execution.

## Decision Tree

```text
1. Is the task tiny, local, and low risk?
   yes -> DIRECT
   no  -> continue

2. Did the user explicitly require exactly one external worker for a low-risk
   non-semantic task?
   yes -> LITE
   no  -> continue

3. Are there independent workstreams large enough to run separately?
   yes -> FULL with coordination_mode: delegate_full
   no  -> continue

4. Is the risk mainly semantic uncertainty, protocol design, permissions,
   schema contracts, security boundaries, or competing design choices?
   yes -> FULL with coordination_mode: moa_review or moa_design
   no  -> continue

5. Do you need to compare candidate patches before selecting one?
   yes -> FULL with coordination_mode: moa_patch, then moa_synthesis
   no  -> DIRECT or SPLIT

6. Is the task too broad, context-heavy, or likely to need more than two repair
   rounds?
   yes -> SPLIT
```

`scripts/afc-route.py` remains the binding deterministic gate for
`DIRECT / LITE / FULL / SPLIT`. `coordination_mode` is optional metadata inside
a `FULL` task; it does not replace the route decision.

## Route Meanings

| Route | Use when | Avoid when |
| --- | --- | --- |
| `DIRECT` | The coordinator can finish faster and safer than coordination | A second model would materially reduce semantic risk |
| `LITE` | One external worker is explicitly needed for one low-risk non-semantic task | The task is semantic, risky, or needs synthesis |
| `FULL` + `delegate_full` | Different workers own different independent workstreams | Workers would edit overlapping files |
| `FULL` + `moa_review` | Multiple workers independently review the same decision surface | The task is a trivial typo or obvious mechanical edit |
| `FULL` + `moa_design` | Multiple workers propose alternative designs | The implementation path is already decided |
| `FULL` + `moa_patch` | Multiple workers produce isolated candidate diffs for comparison | Candidate diffs would collide in one workspace |
| `FULL` + `moa_synthesis` | A synthesis pass compares reports and recommends a final direction | There is only one report or no real conflict |
| `SPLIT` | The task is too large or ambiguous to assign safely | The task is already bounded |

## MOA Versus Delegation

Delegation is parallel division of labor. MOA is independent judgment on the
same decision surface.

Use delegation when the work naturally splits:

```text
Worker A: frontend
Worker B: backend
Worker C: tests
Coordinator: integration verdict
```

Use MOA when the same decision needs independent evidence:

```text
Worker A: review routing policy
Worker B: review routing policy
Worker C: review routing policy
Coordinator: compare agreement, contradiction, evidence quality, and risk
```

Do not label ordinary parallel implementation as MOA. The value of MOA comes
from independent candidate judgment, not from worker count.

