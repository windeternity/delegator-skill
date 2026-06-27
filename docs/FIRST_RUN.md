# First Run

New to Delegator? Read this once. It is the single entry point that explains
what happens the first time you ask the agent to delegate, what the agent will
ask you for, and where your answers are stored.

One principle holds everything together:

> The source you installed is generic — no model, CLI, account, or path is
> hard-coded. On your first delegation the agent interviews you once, records
> your answers into this project's local `.agent-inbox/`, and reuses them on
> every later call. **What it needs from you depends on your automation level.**

The deeper references (`docs/QUICKSTART.md`,
`references/session-bootstrap-gate.md`,
`references/coordination-automation-levels.md`,
`references/unknown-model-discovery.md`) all support this one flow. Start here.

## 1. What you have after install

- **Coordinator-only.** Only the coordinator carries the skill. Workers install
  nothing — each worker receives one task file and one copy-paste line.
- **Generic by design.** The installed files contain neutral placeholders
  (`<Agent Name>`, `<Model>`, `<CLI>`, `<PROJECT_ROOT>`), never your real
  workers, accounts, or paths. Your specifics live only in your project-local
  `.agent-inbox/`, never in the shared skill.

Install steps are in `README.md` / `README.zh-CN.md`. Come back here for the
first delegation.

## 2. The first-trigger CAL choice and the first-delegation interview

Two separate one-time steps, at different moments:

- **CAL level (first skill trigger).** The very first time you invoke the skill
  on a project, the agent explains the CAL-1/CAL-2/CAL-3 distinction in a few
  lines and asks you to pick a default. This is lightweight and runs once
  regardless of routing (even for a `DIRECT` task). Once recorded, it is reused
  and never re-asked.
- **Resource/roster interview (first external dispatch).** The first time a
  task is routed to an **external worker**, the agent runs a one-time bootstrap
  before writing any task files or dispatching anyone. It does **not** run for
  tasks the agent does directly (`DIRECT` route) — those need no worker, so
  there is nothing to interview about.

The interview is one compact block:

```text
Session Bootstrap:
- Existing resources: <tools/models/accounts/runtimes you already have>
- Available now: <usable workers, CLIs, providers, local runtimes>
- Model preference order: <preferred models and fallbacks>
- Avoid / unavailable: <models or routes to avoid, with reason>
- Capability limits: <anything the agent must not assume>
- Automation level (CAL): <CAL-1 | CAL-2 | CAL-3>   (default already chosen at first trigger; confirm or change here)
- Record these as this project's default until I ask to change them?
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
  worker — it only hands you text to forward. So any model or account works,
  even an unknown or chat-only model: the agent just needs a label to address
  the handoff to. A capability smoke test is *optional* and only about whether
  the model is good enough for the task (see §6).
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
| CAL level, resources, model order, avoid list, smoke status, confirmed date | `.agent-inbox/AGENT_ROSTER.md` — `SESSION PREFERENCES` block near the top | Project-local default |
| One-line summary of the above | `.agent-inbox/events.jsonl` — `ROSTER_UPDATED` event | Append-only log |
| CAL-3 invoke bindings | `.agent-inbox/invoke-recipes.json` | Local only — never copied into a public skill package |

**Never recorded:** secrets, tokens, API keys, account identifiers, or private
API details. The recorded preference is a routing input, not an authority grant
— capability, safety, permission scope, worktree locks, and evidence
requirements still override your stated preference when they conflict.

## 6. Reuse and change

- Recorded preferences become this project's default. The agent does **not**
  re-ask them every task or every thread.
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
# Check if CAL default is already recorded (exit 0 = yes, 1 = no)
python -B scripts/afc-first-run-config.py --inbox <PROJECT_ROOT>/.agent-inbox --check-only

# Print the standard first-run questionnaire
python -B scripts/afc-first-run-config.py --print-questionnaire

# Get a conservative CAL recommendation based on described resources
python -B scripts/afc-first-run-config.py --recommend --resources "..." --available-now "..."

# Write preferences (validates CAL, rejects secrets, records event)
python -B scripts/afc-first-run-config.py --inbox <PROJECT_ROOT>/.agent-inbox \
    --default-cal CAL-2 \
    --resources "Claude Code CLI, codex CLI" \
    --available-now "worker-cli, backup-cli" \
    --model-order "primary-model, review-model" \
    --avoid "deprecated-model (unavailable)" \
    --capability-limits "no browser automation" \
    --confirmed-at 2026-06-27
```

The helper writes into the `SESSION PREFERENCES` comment block in
`AGENT_ROSTER.md` and appends a `ROSTER_UPDATED` event to `events.jsonl`. It
never records secrets, tokens, API keys, or account identifiers — any such
input is rejected before writing.

The `--check-only` mode is the cheapest way for the coordinator to implement the
First-Run CAL Init presence check: one subprocess call, zero roster hydration,
exit code only.

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
