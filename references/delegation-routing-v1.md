# Delegation Routing v1

Status: active and binding for new assignments.

For the product-level decision tree above this deterministic router, see
`references/coordination-routing-policy.md`.

## Invariant

Route before reading `AGENT_ROSTER.md`, templates, `.agent-inbox/`, reports, or
worker-specific material. A task that routes `DIRECT` must not pay coordination
startup cost.

```powershell
python -B scripts/afc-route.py `
  --estimated-direct-minutes <N> `
  --independent-workstreams <N> `
  --smallest-workstream-minutes <N> `
  --specialized-capability <yes|no> `
  --high-risk-independent-review <yes|no> `
  --external-worker-required <yes|no> `
  --semantic-change <yes|no> `
  --expected-rounds <N> `
  --context-bytes <N> `
  --available-distinct-models <N> `
  --blast-radius <low|medium|high> `
  --json
```

Fill `--blast-radius` from `scripts/afc-blast-radius.py --files <declared paths>`
so the MOA value gate rests on a scriptable signal, not a coordinator opinion.

## Decision Table

| Decision | Deterministic condition | Action |
|---|---|---|
| `DIRECT` | No FULL condition and no safe LITE exception | Stop loading Delegator state; execute directly |
| `LITE` | User requires an external worker; one non-semantic workstream; >=15 minutes; one expected round | Generate one no-inbox handoff with `afc-lite.py` |
| `FULL` | Direct estimate >=240 minutes; or >=2 independent streams totaling >=180 minutes with each >=60; or unavailable capability; or high-risk independent review; or MOA collaboration (semantic change + blast radius medium/high + >=2 distinct models + >=20 minutes) | Use task/report protocol; obey `max_workers` |
| `SPLIT` | Inline context >4 KB or expected rounds >2 | Tighten/split the task or replace context with pointers, then route again |
| `INVALID` | Missing/negative/unknown input or invalid override | Correct the routing evidence |

An explicit FULL override is allowed only with a reason of at least 12
characters and is recorded as `EXPLICIT_OVERRIDE`.
For multiple workstreams, omitted smallest-workstream evidence is treated as
zero rather than inferred from total effort; the router does not guess that
every stream clears the 60-minute floor.

## Frequency Budget

For one FULL batch:

1. One route decision before coordination reads.
2. One roster confirmation per session, not per worker.
3. One dispatch batch.
4. One `afc-intake.py --task-id <ID> --json` call after reports arrive, with
   repeated task IDs for the current batch.
5. One consolidated repair request containing all known findings.
6. One integrated quality gate after source changes converge.
7. One final verdict/close boundary.

Do not rerun validators, Git state, report reads, or full tests when only
coordination metadata changed.

## Assignment Spec

`afc-assign.py` requires `routing.*` evidence for new work and refuses a route
other than FULL. Example:

```yaml
routing.estimated_direct_minutes: 240
routing.independent_workstreams: 2
routing.smallest_workstream_minutes: 90
routing.specialized_capability: no
routing.high_risk_independent_review: no
routing.external_worker_required: no
routing.semantic_change: yes
routing.expected_rounds: 1
routing.context_bytes: 900
routing.requested_mode: auto
routing.available_distinct_models: 1
routing.blast_radius: medium
```

`--legacy-unrouted` exists only to migrate old fixtures or active tasks. It must
not be used to bypass routing for new coordination.

## MOA (multi-model collaboration) gate

MOA is a first-class reason to choose FULL: substantive work benefits from
being cross-checked across distinct models. To stay objective (never an
inflatable coordinator score) the gate is a three-layer AND:

```
MOA = semantic_change == yes
      AND blast_radius in {medium, high}            # value
      AND available_distinct_models >= 2            # feasibility
      AND estimated_direct_minutes >= MOA_MIN_MINUTES (20)  # economy
```

- The feasibility layer defaults dormant (`available_distinct_models` = 1). The
  coordinator must declare its roster; otherwise MOA never fires and routing is
  identical to the pre-MOA behavior. This is the safety valve against collapsing
  into always-FULL.
- The value layer also does real filtering: `blast_radius` defaults to `unknown`,
  which does NOT satisfy the gate. The coordinator must run
  `afc-blast-radius.py` and pass the result (low/medium/high). Defaulting to
  medium without classification is not a valid MOA route.
- An MOA-only FULL defaults to `max_workers = 2` (a small cross-check set); it
  only rises toward 3 when real parallelism is also present.
- If a task is unsafe for LITE but satisfies the MOA gate, it promotes to FULL
  rather than self-executing: collaboration value outranks a lite preference.

### blast_radius tiers

Fill `routing.blast_radius` with `scripts/afc-blast-radius.py --files ...` so the
value rests on what the declared files actually are, not a coordinator guess:

- `high`: a declared file matches a sensitive domain (auth/payment/migration/
  lock/concurrency/token/secret), is imported by >=3 other files, or has
  dependents but no test sibling.
- `low`: docs/tests, a module with a test sibling, or an isolated module.
- `medium`: fallback when files are examined but emit no high or low signal.
  Note: an OMITTED `routing.blast_radius` defaults to `unknown` (not medium),
  and `unknown` does not satisfy the MOA gate — the coordinator must run the
  classifier and pass a real tier.

## Evidence Basis

The P2B same-task benchmark recorded a 4.22x coordinator-only weighted-token
cost for a three-worker FULL run versus direct execution. Most of the delta came
from replaying a growing context, repeated intake/validation commands, and
schema-only repair rounds.

The MOA re-weight accepts higher token cost on substantive work in exchange for
multi-model cross-check quality, gated by the three-layer AND above so it never
collapses into always-FULL and reintroduces the measured 4.22x overhead.
