# First Run

New to Delegator? Read this once. It is the single entry point that explains
what happens the first time you ask the agent to delegate, what the agent will
ask you for, and where your answers are stored.

One principle holds everything together:

> The source you installed is generic — no model, CLI, account, or path is
> hard-coded. Delegator stores your default CAL and external-worker roster in
> the install-local `LOCAL_ROSTER.md`, shared across projects. Project-local
> `.agent-inbox/AGENT_ROSTER.md` is used only as an explicit project override.

The deeper references (`docs/QUICKSTART.md`,
`references/session-bootstrap-gate.md`,
`references/coordination-automation-levels.md`,
`references/unknown-model-discovery.md`) all support this one flow. Start here.

## 1. What you have after install

- **Coordinator-only.** Only the coordinator carries the skill. Workers install
  nothing — each worker receives one task file and one copy-paste line.
- **No workers are created by install.** While Delegator is active, a
  current-session subagent, built-in helper, internal `multi_agent` call, or
  chat-only call is never used for exploration, review, implementation, or
  fallback. `DIRECT` means the coordinator itself executes.
- **Generic by design.** The installed files contain neutral placeholders
  (`<Agent Name>`, `<Model>`, `<CLI>`, `<PROJECT_ROOT>`), never your real
  workers, accounts, or paths. Your specifics live in install-local `LOCAL_*`
  files or an explicitly marked project override, never in published sources.
- **Placeholders are not configuration.** A roster that still contains template
  worker placeholders is invalid for LITE, FULL, or CAL dispatch.

Install steps are in `README.md` / `README.zh-CN.md`. Come back here for the
first delegation.

## 2. The first-trigger CAL choice and the first-delegation interview

Two separate one-time steps, at different moments:

- **CAL level (first skill trigger, once per user).** The very first time you
  invoke the skill, the agent first gives a one-time orientation: what the
  skill is for (it coordinates EXTERNAL workers through bounded local task/report
  files under your control — installing it creates no workers) and the three CAL
  modes with per-mode trade-offs (`references/coordination-automation-levels.md`
  §"Quick Comparison"). Only then does it ask you to pick a default and writes
  it to the install-local `LOCAL_ROSTER.md` in the Skill directory, reused by
  every project. This is lightweight and runs once regardless of routing (even
  for a `DIRECT` task). Once recorded, it is reused and never re-asked.
- **Resource/roster interview (first external dispatch).** The first time a
  task is routed to an **external worker** with no usable roster resolved, the
  agent runs a one-time bootstrap before writing any task files or dispatching
  anyone. It does **not** run for `DIRECT` tasks. By default the roster is the
  install-local `LOCAL_ROSTER.md` (shared across projects); a project
  `.agent-inbox/AGENT_ROSTER.md` is read only as an explicit override (add the
  `<!-- AFC_ROSTER_SCOPE: project-override -->` marker). If the resolved roster
  is missing, empty, placeholder-only, incomplete, or lacks the selected worker,
  dispatch stops and the agent asks for the missing configuration.

The interview is one compact block:

```text
External Dispatch Bootstrap:
- Existing resources: <tools/models/accounts/runtimes you already have>
- Available now: <usable workers, CLIs, providers, local runtimes>
- Model preference order: <preferred models and fallbacks>
- Avoid / unavailable: <models or routes to avoid, with reason>
- Capability limits: <anything the agent must not assume>
- Automation level (CAL): <CAL-1 | CAL-2 | CAL-3>   (default already chosen at first trigger; confirm or change here)
- Record these in LOCAL_ROSTER.md as the default until I ask to change them?
```

You confirm or adjust, then the agent records and reuses your answers. If your
opening message already names the level and the worker(s) to use, the agent
records that and proceeds without a separate confirmation round.

## 3. Pick your automation level — it decides what the agent needs

The one question that changes everything: **does the coordinator launch the
worker itself, or do you relay the handoff to the worker?**

| Level | Who launches the worker | What you must provide | CLI verification |
|---|---|---|---|
| **CAL-1** Manual Relay | You (paste the handoff, then tell the agent it is done) | A name to address the handoff to, model preference, CAL | **None** |
| **CAL-2** Auto Intake | You (paste the handoff; the agent auto-detects the report) | Same as CAL-1 | **None** |
| **CAL-3** Full Auto | The coordinator, via a local CLI on your machine | A **callable** Agent/CLI per worker **plus** its exact invoke binding | **Required, before first dispatch and at every use** |

### Why the difference

- In **CAL-1 / CAL-2 you are the transport layer.** The agent never runs your
  worker — it only hands you text to forward. The target may be an external
  chat, tool, IDE, CLI, model, or app session, but it must be recorded in the
  roster as an external route with permissions and report-writing expectations.
  A current-session subagent or internal helper is never valid. A capability
  smoke test is *optional* and only about whether the external route is good
  enough for the task (see §6).
- In **CAL-3 the agent runs a process on your machine.** A wrong or missing CLI
  binding does not produce a polite error — it silently launches the wrong model
  or fails mid-batch. That is why CAL-3 turns CLI availability and verification
  into a **hard requirement**, not a preference.

CAL-1 is the safe default and works everywhere. CAL-2 removes your "done"
message when the coordinator can run a foreground watcher. CAL-3 may be set as
a project default — but it is the highest-risk choice, and its §4 CLI
verification still gates the first dispatch.

## 4. CAL-3 extra requirements (when you choose CAL-3)

When you choose CAL-3 — as a default at first trigger or as a one-off — the
agent must confirm all of the following before the first automatic dispatch:

1. **A real callable CLI per worker alias.** Each alias must resolve to a CLI
   that exists on `PATH` or through a recorded launcher. No callable CLI → that
   worker cannot run under CAL-3; fall back to CAL-1/CAL-2 for it.
2. **A recorded invoke binding.** The agent records which environment/home,
   provider, endpoint class, model, and reasoning effort the alias actually
   uses — in the project-local recipe/roster, **never** secrets or tokens. An
   ambiguous binding stops the run; the agent will not fall back to a default
   user profile.
3. **Verification, not trust.** The agent probes to confirm the CLI and binding,
   the dispatcher launches with an explicit argument list (no shell string),
   captures stdout/stderr as **untrusted** input, and treats *only a
   schema-valid report file at the exact expected path* as completion — never
   stdout text or a chat-only "done".
4. **High-risk actions stay manual.** Commit, push, merge, deploy, destructive
   cleanup, secrets handling, and permission escalation require explicit
   per-action authorization even under CAL-3.

For long CAL-3 dispatches (roughly 10+ minutes), do not wait silently for the
final timeout. During the run, check live artifacts such as
`.agent-inbox/artifacts/cal3/<TASK_ID>/stderr.log`, `stdout.log`, and
`.agent-inbox/events.jsonl`; Codex-style workers often write their live trace to
stderr while stdout stays empty. Use `status.json` after dispatch finishes.
Logs and heartbeats are progress/debug evidence only — completion still
requires the exact schema-valid report file.

If a worker needs a local SQLite/Chroma/vector-store directory outside the task
workspace, configure that writable root explicitly in the local Codex sandbox
config before dispatch. Delegator records the need, but does not auto-expand
filesystem write boundaries.

Codex CAL-3 recipes default `network_access` to `none`. Set
`AFC_CAL3_CODEX_NETWORK_ACCESS=allowed` before probing only after local Codex
`workspace-write` network access is explicitly configured.

Generic commands (replace `<PROJECT_ROOT>` and `<TASK_ID>`):

```text
# Detect installed headless CLIs and write a local recipe draft (verification step)
python -B scripts/afc-cal3-probe.py --inbox <PROJECT_ROOT>/.agent-inbox --write

# Dispatch one task through its verified CLI worker
python -B scripts/afc-cal3-dispatch.py --inbox <PROJECT_ROOT>/.agent-inbox --task-id <TASK_ID> --max-attempts 2
```

Full detail: `references/coordination-automation-levels.md` (CAL-3 section) and
`docs/QUICKSTART.md` §10.

## 5. What gets recorded, and where

| What | Where | Notes |
|---|---|---|
| CAL level, resources, model order, avoid list, smoke status, confirmed date | install-local `LOCAL_ROSTER.md` | User-profile default, shared across projects |
| External worker rows, permissions, access path, report-writing ability | install-local `LOCAL_ROSTER.md` | Default roster before external dispatch |
| Explicit project-specific differences | `.agent-inbox/AGENT_ROSTER.md` with `AFC_ROSTER_SCOPE: project-override` | Optional project override |
| Project task/report lifecycle events | `.agent-inbox/events.jsonl` | Project-local append-only log |
| CAL-3 invoke bindings | install-local `LOCAL_INVOKE_RECIPES.json` by default; `.agent-inbox/invoke-recipes.json` for a project override | Local only — never copied into a public skill package |

**Never recorded:** secrets, tokens, API keys, account identifiers, or private
API details. The recorded preference is a routing input, not an authority grant
— capability, safety, permission scope, worktree locks, and evidence
requirements still override your stated preference when they conflict.

## 6. Reuse and change

- Recorded preferences become the install-local user-profile default across
  projects. The agent presence-checks once per coordinator session but does not
  re-ask when the default exists.
- It re-confirms only when you ask to change them, a route becomes unavailable,
  the roster conflicts with the current conversation, or a task needs a
  capability you did not record.
- You can switch CAL level mid-run: downgrades apply immediately; upgrades to
  CAL-3 require the §4 checks first.

## 7. A model the agent has never seen

If you name a model, CLI, provider, or local runtime that is not in the routing
references, the agent does not reject it and does not guess its ability from its
name. It preserves your exact label, classifies the evidence level, maps it to
capability buckets, and starts with a small read-only smoke test before serious
work. See `references/unknown-model-discovery.md`.

## 8. First-run configuration helper

The script `scripts/afc-first-run-config.py` automates the presence check and
preference recording described in §2–§5. It is optional — the agent can do the
same steps inline — but useful for scripted or non-interactive setup.

```text
# Literal first command: check install-local CAL default (exit 0 = yes, 1 = no)
python -B scripts/afc-first-run-config.py --check-only

# Print the standard first-run questionnaire
python -B scripts/afc-first-run-config.py --print-questionnaire

# Get a conservative CAL recommendation based on described resources
python -B scripts/afc-first-run-config.py --recommend --resources "..." --available-now "..."

# Write install-local preferences (validates CAL and rejects secrets)
python -B scripts/afc-first-run-config.py \
    --default-cal CAL-2 \
    --resources "Claude Code CLI, codex CLI" \
    --available-now "worker-cli, backup-cli" \
    --model-order "primary-model, review-model" \
    --avoid "deprecated-model (unavailable)" \
    --capability-limits "no browser automation" \
    --confirmed-at 2026-06-27
```

The helper writes the install-local `LOCAL_ROSTER.md` by default and writes no
project event for that user-profile choice. Pass an explicit project override
only when project-specific routing is intended. It never records secrets,
tokens, API keys, or account identifiers.

The `--check-only` mode is the cheapest way to implement the First-Run CAL Init
presence check: one subprocess call and zero roster hydration. An unconfigured
result exits 1 and emits `next_action: ASK_CAL`; routing must not run first.

Use `--roster-status` only after routing selects external dispatch. It performs
the full read-only gate and reports `missing`, `placeholder_only`, `incomplete`,
or `usable`.

## 9. Session orientation: one command to know what to do next

At the start of any coordinator session, use `afc-snapshot.py --next-action`
to get a compact summary of what requires attention:

```powershell
python -B scripts/afc-snapshot.py --next-action .agent-inbox
```

Returns a bounded read-only summary:

```text
route_required: yes | no
cal_default_recorded: yes | no
active_tasks: N
new_reports: N
rejected_reports: N
stale_tasks: N
recommended_next_action: route_direct | ask_cal | review_report | wait_for_reports | close_task | no_action
read_next:
  - <up to 3 most important file paths>
run_next:
  - <at most 1 recommended command>
```

This command is optional but removes coordinator ambiguity at session start. It
is designed to be cheap: it scans the inbox directory, reads frontmatter only,
does not read full report bodies, and calls no validators by default.

Add `--json` to get machine-readable output for integration.

## Where to go next

- `docs/QUICKSTART.md` — minimal end-to-end setup and the first task/report
  cycle.
- `references/session-bootstrap-gate.md` — the exact bootstrap decision flow and
  recording format.
- `references/coordination-automation-levels.md` — full CAL-1/2/3 behavior,
  risks, and switching rules.
- `references/unknown-model-discovery.md` — onboarding an unfamiliar model or
  CLI safely.
- `docs/HYDRATION_GUIDE.md` — turning the templates into a live `.agent-inbox/`.
