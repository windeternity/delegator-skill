# Coordination Routing Policy

Status: active guidance for deciding when and how to use AFC.

This policy sits above CAL-1, CAL-2, and CAL-3. It decides whether the
`agent-file-coordination` skill should be used at all, then selects the
coordination automation level, then selects a worker route only when needed.

## Decision Layers

| Layer | Question | Output |
| --- | --- | --- |
| Skill activation | Is coordination worth its startup cost? | `NO_SKILL`, `DIRECT`, `LITE`, `FULL`, or `SPLIT` |
| CAL route | If coordination is useful, how automated should the loop be? | `CAL-1`, `CAL-2`, or opt-in `CAL-3` |
| Worker route | If CAL-3 starts workers, which worker should run? | See `references/cal3-default-routing-policy.md` |

## Layer 1: Skill Activation

Use AFC only when coordination changes the outcome enough to pay for its
overhead. The default is direct execution.

| Route | Use when | Do not do |
| --- | --- | --- |
| `NO_SKILL` | The task is a short answer, command lookup, simple explanation, or ordinary local edit with no external worker value. | Do not load `.agent-inbox/`, roster, task templates, or worker reports. |
| `DIRECT` | The coordinator can finish faster and safer than delegation. | Do not create coordination artifacts to justify a direct task. |
| `LITE` | The user explicitly needs one external worker for one bounded, low-risk, non-semantic workstream. | Do not hydrate the full inbox or create a multi-worker protocol batch. |
| `FULL` | Work is large, parallel, specialized, high-risk enough for independent review, or valuable for multi-model collaboration. | Do not skip routing evidence; do not exceed the worker budget. |
| `SPLIT` | The request is too broad, has too much inline context, or would require too many repair rounds. | Do not force it into FULL until the task is bounded. |

`scripts/afc-route.py` is the deterministic gate for `DIRECT`, `LITE`, `FULL`,
and `SPLIT`. Run it before reading roster, inbox, task, report, or worker
profile state.

## Layer 2: CAL Route

Choose a CAL level only after Layer 1 says coordination is worth using.

Exception: the CAL default is chosen once, at the first skill trigger, before
Layer 1 — a presence check on `.agent-inbox/AGENT_ROSTER.md` only, which is the
sole exception to the route-before-read invariant (see `SKILL.md` First-Run CAL
Init). Once recorded, it governs Layer 2 and is not re-asked.

| CAL | Use when | Default posture |
| --- | --- | --- |
| `CAL-1` | Maximum human control is needed, or watcher/worker automation is unavailable. | Safe baseline. |
| `CAL-2` | The user can still choose workers manually, but the coordinator should auto-intake reports. | Preferred normal coordination mode when foreground watcher is reliable. |
| `CAL-3` | Low-risk local dogfood or trusted disposable/dedicated workspaces where worker auto-start is explicitly useful. | Selectable default; first dispatch still CLI-verification-gated. |

CAL level does not expand permission. Task `permission_scope`, locked areas,
and explicit release authorization remain binding.

CAL workers must be external to the current coordinator session. Do not satisfy
a requested worker or model alias by launching a current-session subagent or
`multi_agent.spawn_agent`.

## Layer 3: Worker Route

Worker routing applies only after CAL-3 is selected. Current evidence-based
defaults are in `references/cal3-default-routing-policy.md`:

- `opencode`: quick bounded local validation and low/medium-risk edit chores.
- `claude`: review, docs, protocol reasoning, and risk analysis.
- `codex`: fallback/manual only.
- `mimo`: excluded.

For CAL-1 and CAL-2, worker names or model labels still must bind to external
roster entries that the user relays to. For CAL-3, they must bind to dispatcher
recipes.

## Default Procedure

1. Classify the task shape and declared files.
2. If the task is small or directly answerable, use `NO_SKILL` or `DIRECT`.
3. If delegation might help, run `scripts/afc-blast-radius.py` for declared
   files, then `scripts/afc-route.py`.
4. If route is `DIRECT`, stop AFC startup and execute directly.
5. If route is `LITE` or `FULL`, choose CAL level.
6. If CAL-3 is selected, choose a worker from the CAL-3 routing policy.
7. Keep commit, push, release, deploy, destructive actions, secrets, and
   permission expansion behind explicit authorization.

## Promotion Boundary

CAL-3 may be scored as 90 for opt-in, low-risk local dogfood after:

- direct expected-report validation works after worker process exit;
- watcher compatibility is secondary and non-authoritative;
- default worker routes are evidence-based;
- at least one real bounded edit run succeeds with a schema-valid report.

That is still not the same as making CAL-3 the normal project default. Normal
default promotion requires clean cost benchmarking and more non-doc edit
samples.
