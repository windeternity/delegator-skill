# Hydration Guide

This guide explains how to hydrate the source-level placeholder templates into project-local coordination files.

## Overview

The `templates/` directory contains reusable, model-agnostic, vendor-neutral template files. Each template uses `<PLACEHOLDER>` markers for values that must be filled in per project.

Hydration is the process of replacing those placeholders with your project-local agent roster, paths, preferences, and coordination state.

Placeholder values are valid only while editing templates. A roster that still
contains placeholder worker routes is not usable for `LITE`, `FULL`, or CAL
dispatch. Installing Delegator also does not create external workers: a
current-session subagent, built-in helper, or internal `multi_agent` call is
not an AFC worker route.

## When To Hydrate

### First Use

When you first use Delegator on a new project, hydrate task/status/lock/event
templates into `.agent-inbox/`. Keep the default worker roster and CAL choice in
the install-local `LOCAL_ROSTER.md`. Hydrate `AGENT_ROSTER.md` only when the
project needs an explicit override, and add the project-override marker.

### Repeat Use

Before assigning external agents on an existing project:

1. Resolve the roster: install-local `LOCAL_ROSTER.md` by default, or an
   explicitly marked `.agent-inbox/AGENT_ROSTER.md` override.
2. Summarize the current roster and preferences to the user.
3. If no resource inventory or CAL/execution preference is recorded, ask the
   user to choose before dispatch.
4. Ask whether the roster is still valid, or whether agents, tools, models,
   accounts/runtimes, capabilities, or CAL preference have changed.
5. If the roster is stale, update it before writing new task files.

For `DIRECT`, do not run this full roster read. Route-first still applies; the
only permitted pre-route exception is the cheap first-run CAL presence check.

Do not skip this step. Agent availability, model versions, and tool access change frequently.

## First-Use Hydration Flow

### Step 1: Gather Agent Inventory

Ask the user:

```text
Before I assign agent tasks, tell me what you currently have available:
1. Canonical Agent Names: Reviewer / Implementer / Runtime-Smoke / Docs-Writer / Merge-Check / other project-local names.
2. Tool and model behind each name: Codex / Claude Code / OpenCode / Gemini CLI / Cursor / Copilot / Cline / Roo / Kilo / local tools / browser chat / other.
3. Existing resources: accounts, providers, CLI aliases, local runtimes, browser tools, and any known credit/quota constraints.
4. Available now: which of those routes are usable for this project, paused, unavailable, or untested.
5. Capabilities per agent: can edit files, run commands, use browser/visual input, create worktrees, or only review read-only.
6. Report capability per agent: can write report files to the specified Report Path / chat-only / unknown.
7. Worktree capability per agent: can_create / can_use_existing / read_only_shared / manual_needed / unknown.
8. Role per agent: coordinator / planner / implementer / reviewer / smoke / docs / research / other.
9. Which agent is the coordinator or final judge?
10. Which model/tool pair do you prefer, which fallbacks are acceptable, and which should be avoided for this project?
11. Which coordination level should be the project default: CAL-1 manual relay, CAL-2 auto intake with a foreground watcher, or CAL-3 full auto with verified CLI bindings?
```

If the user's message already provides enough information, proceed directly.

### Step 2: Create The Inbox

```powershell
mkdir <PROJECT_ROOT>/.agent-inbox
```

### Step 3: Hydrate The Roster

For an explicit project override, copy `templates/TEMPLATE_ROSTER.md` to
`<PROJECT_ROOT>/.agent-inbox/AGENT_ROSTER.md` and add the exact
`AFC_ROSTER_SCOPE: project-override` marker described in the template. Otherwise configure
`templates/TEMPLATE_LOCAL_ROSTER.md` once in the installed Skill directory.

User-specific worker names, model labels, and CLI aliases are recorded in the
install-local roster, an explicit project override, or local CAL-3 invoke
recipes. Do not add them to published skill sources.

Replace all `<PLACEHOLDER>` values:

| Placeholder | Replace With |
| --- | --- |
| `<COORDINATOR_NAME>` | The canonical name of the coordinator agent |
| `<WORKER_NAME_1>`, `<WORKER_NAME_2>` | Canonical names of worker agents |
| `<ROLE>` | Role per agent (coordinator / planner / implementer / reviewer / smoke / docs / research / other) |
| `<TOOL_NAME>` | The tool behind each agent name |
| `<MODEL_NAME>` | The model behind each agent name |
| `<PROVIDER_OR_PATH>` | How to access the agent (local session, API, browser, etc.) |
| `<PROTOCOL_MODE>` | full-skill / worker-brief / task-only / manual-paste / unknown |
| `<YES_OR_NO>` | yes or no |
| `<COMMAND_LEVEL>` | none / read_only / tests_only / bounded |
| `<WORKTREE_CAPABILITY>` | can_create / can_use_existing / read_only_shared / manual_needed / unknown |
| `<BEST_USE>` | What this agent does best |
| `<AVOID>` | What to avoid assigning to this agent |
| `<NOTES>` | Any additional notes |

Add or remove rows as needed. Keep exactly one coordinator with `Coordinator Authority: yes`.

Record the user's confirmed execution preference in the local roster without adding schema fields. A compact note near the top is enough:

```markdown
<!-- SESSION PREFERENCES
Default CAL: CAL-2
Execution preference: use <IMPLEMENTER_AGENT> for bounded edits, <REVIEWER_AGENT> for independent review; avoid <AGENT_OR_MODEL> for high-risk changes.
Available resources: <TOOLS_PROVIDERS_ACCOUNTS_LOCAL_RUNTIMES_AND_LIMITS>
Model preference order: <PREFERRED_MODELS_AND_FALLBACKS>
Avoid / unavailable: <MODELS_TO_AVOID_PAUSED_ROUTES_OR_KNOWN_LIMITS>
Smoke tests: <LAST_KNOWN_SMALL_TEST_OR_UNKNOWN>
Confirmed: <YYYY-MM-DD>
Change policy: keep these defaults until the user asks to change them or a route becomes unavailable.
-->
```

### Step 4: Hydrate Status Board And Locks

Copy `templates/TEMPLATE_STATUS_BOARD.md` to `<PROJECT_ROOT>/.agent-inbox/STATUS.md`.

Copy `templates/TEMPLATE_WORKTREE_LOCKS.md` to `<PROJECT_ROOT>/.agent-inbox/WORKTREE_LOCKS.md`.

Replace placeholders. If no tasks are assigned yet, it is fine to have no
active task files, but the roster itself must contain at least one concrete
external worker row before external dispatch.

Roster usability checklist:

- `Default CAL` is a concrete `CAL-1`, `CAL-2`, or `CAL-3`.
- At least one non-coordinator external worker row is hydrated.
- Agent name, role, tool/model label, provider/access path, protocol mode,
  edit/command/report permissions, best use, and avoid/limits are concrete.
- CAL-1/CAL-2 user-relay routes point to an external chat/tool/model/session,
  not the coordinator's current-session helper.
- CAL-3 routes have callable invoke recipes and probe evidence.
- The worker can write the expected report/evidence path; chat-only "done" is
  not accepted as completion evidence.

### Step 5: Create Event Log

Create `<PROJECT_ROOT>/.agent-inbox/events.jsonl` with the initial roster event:

```jsonl
{"schema":"agent-file-coordination/event","schema_version":"0.1.0","event_id":"evt-001","event_type":"ROSTER_UPDATED","created_at":"<YYYY-MM-DD>","summary":"Created project agent roster and recorded default CAL/execution preferences from template hydration."}
```

### Step 6: Assign Tasks

When ready to assign work, copy `templates/TEMPLATE_TASK.md` for each worker. Fill in:

- `task_id`, `agent_name`, `role`, `protocol_mode`, `coordinator_authority`
- `permission_scope` — match the worker's actual capabilities
- `workspace` — use the real worktree path, branch, and locked file area
- `validation_tier` — match the task's risk level
- `report_path` — the actual path where the worker should write its report
- Task body sections: Purpose, Non-Goals, Acceptance Criteria, Evidence To Report

For fixture, validator, poller, stateful, or test-runner tasks, add an explicit repeated-run criterion such as `3 consecutive serial runs pass from a clean or deterministically reset state`. Do not accept worker self-reports of "all tests passed" without coordinator reproduction when the result controls a GO/PARTIAL/RED decision.

Before dispatch, cross-check `locked_files_or_areas` against every `ACTIVE`
row in `.agent-inbox/WORKTREE_LOCKS.md`. Record `no_overlap`,
`intentional_overlap`, or `conflict_blocked` in the task/event evidence. Resolve
`conflict_blocked` before assignment. Prefer routed `afc-assign.py` generation
over hand-editing the template.

The task's `status` frontmatter field is coordinator-owned. The `DRAFT → ASSIGNED → RUNNING → REPORTED → REVIEWING → NEEDS_FIX → CLOSED_*` transitions are set by the coordinator or the assignment script, not by the worker. Workers deliver the report file at the assigned `Report Path`; the coordinator reconciles the report against the task's frontmatter.

Keep the task body worker-name-agnostic. Every section below the frontmatter — Purpose, Non-Goals, Acceptance Criteria, Evidence To Report, Read First — must work for any worker whose `agent_name` matches the frontmatter. A re-routing handoff is a one-line change to `agent_name` and `report_path`; if a body field would force a specific identity, remove the name and rely on the frontmatter fields.

### Step 7: Hand Off To Workers

For each assigned worker, provide one short copy-paste instruction. The handoff must match the user's current conversation language. When using `afc-assign.py`, pass `--handoff-language <TAG>` or set `handoff.language` in the spec. For languages without built-in support, provide `handoff.template` in the spec; without a template the script exits with an error and the coordinator must manually localize.

English:

```text
You are <AGENT_NAME>.
Open this existing worktree as the project: <WORKSPACE_PATH>.
Do not open <COORDINATION_ROOT> as the project.
Do not create another worktree.
Read <absolute-task-file-path>. Execute only this task within its Permission Scope and write your report to the specified Report Path. Do not commit or push.
```

Chinese:

```text
你是 <AGENT_NAME>。
把这个现有 worktree 作为项目打开：<WORKSPACE_PATH>。
不要把 <COORDINATION_ROOT> 作为项目打开。
不要新建 worktree。
读取 <absolute-task-file-path>，只在 Permission Scope 内执行该任务，并把回执写到指定 Report Path。不要 commit/push。
```

Supported built-in language tags: `en` (English), `zh` / `zh-cn` / `zh-tw` (Chinese). For other languages, provide a `handoff.template` in the spec with variables `{agent_name}`, `{ws_path}`, `{inbox_dir}`, `{task_filepath}`, `{report_path}`. Without a template, the script refuses to produce an English fallback and exits with an error — the coordinator must manually localize the handoff in the user's language.

The four paths are distinct: the project/worktree to open (`<WORKSPACE_PATH>`), the task file to read, the report path to write, and the coordination root (`<COORDINATION_ROOT>`, which is a file bus, not a Git workspace). The coordination root must never be opened as the external tool's project. If the task file's `workspace.may_create_worktree` is `no`, the `Do not create another worktree.` / `不要新建 worktree。` line is mandatory; if it is `yes`, drop that line and let the worker create a new worktree under the same project root.

## Machine-State Changes (Coordinator + User Only)

The following actions are coordinator-or-user only, never delegated to a worker, and require an explicit verification step before they are treated as done:

- Installing or upgrading dependencies (`pip install`, `npm install`, `cargo add`, package-manager equivalents, `brew install`, system-level installers).
- Registering or modifying scheduled tasks (`cron`, `systemd` units, `launchd` plists, Windows Task Scheduler entries).
- Changing environment variables (`export`, `.env` writes, shell rc edits, registry edits, secret-manager updates).
- Modifying Git config, SSH keys, GPG keys, signing settings, or authentication tokens.
- Starting, restarting, or stopping services (local daemons, Docker containers, cloud-managed services).
- Changing cloud / billing / permission settings (account-level IAM, project roles, resource quotas).

If a worker discovers that one of these is required to complete its task, it reports the requirement and stops. The coordinator or user performs the change, verifies the result, then re-assigns or resumes the task. The worker's report must not claim that the machine-state change was performed on its behalf.

## Repeat-Use Roster Confirmation

The roster and project-local preferences are reconfirmed before the first external assignment only when they are missing, stale, contradicted, or the user asks to change them. After confirmation, subsequent assignments only re-validate the specific row used (agent, model, tool) plus any paused-route, CAL, or capability changes the user has called out since the last confirmation. The check itself runs as:

1. Read the resolved roster (install-local by default; explicit project
   override only when marked).
2. Present a summary to the user:

```text
Current roster:
- <Agent Name> (<Role>) — <Tool> / <Model> — <Key Capability>
- ...

Recorded default: <CAL-1|CAL-2>; <execution preference summary>.
Is this still accurate? Any agents, tools, models, capabilities, or CAL preference changed?
```

3. If the user confirms, proceed with task assignment.
4. If the user reports changes, update the roster and event log before proceeding.
5. If the roster or default preference is missing, placeholder-only, incomplete,
   or unmatched for the selected worker, stop and run the full first-use
   hydration flow before generating a task or handoff.

### Paused Routes

When a route is paused — for example, an upstream provider is down, a model is rate-limited, a tool entry point is broken, or the user wants a temporary hold on a worker — mark it in the project-local roster rather than deleting the row. A typical entry looks like:

```markdown
| <Agent Name> | <Role> | <Tool> | <Model> | <Provider/Path> | <Protocol Mode> | no | ... | paused: 2026-06-12 reason: "provider 503 since 2026-06-10" |
```

Paused routes are excluded from assignment without losing the capability record. When the route is restored, edit the same row to remove the `paused:` note. Do not create a fresh row for the same worker; do not delete the row and re-add it later — the `paused:` note is the project's memory of the hold.

## Placeholder Reference

All templates use the following placeholder conventions:

| Placeholder | Meaning |
| --- | --- |
| `<PROJECT_ROOT>` | Absolute or relative path to the project being coordinated |
| `<PROJECT_NAME>` | Short project identifier |
| `<AGENT_NAME>` | Canonical agent name from the roster |
| `<COORDINATOR_NAME>` | The coordinator agent's canonical name |
| `<WORKER_NAME_N>` | A worker agent's canonical name |
| `<TOOL_NAME>` | The tool an agent uses (e.g., Codex, Claude Code, local tools) |
| `<MODEL_NAME>` | The model behind an agent (e.g., high-reasoning, code-specialized) |
| `<PROVIDER_OR_PATH>` | How to access the agent |
| `<ROLE>` | Agent role (coordinator / planner / implementer / reviewer / smoke / docs / research / other) |
| `<PROTOCOL_MODE>` | full-skill / worker-brief / task-only / manual-paste / unknown |
| `<COORDINATOR_AUTHORITY>` | yes / no / limited |
| `<TASK_ID>` | Short stable task identifier |
| `<TASK_TITLE>` | Human-readable task title |
| `<LOCK_ID>` | Short stable lock identifier |
| `<REPORT_PATH>` | Path where the worker writes its report |
| `<WORKSPACE_MODE>` | read_only_shared / existing_edit_worktree / dedicated_worktree_required / manual_worktree_needed |
| `<WORKSPACE_PATH>` | Absolute or project-relative workspace path |
| `<WORKTREE_PATH>` | Path to a worktree directory |
| `<BRANCH_NAME>` | Git branch name |
| `<FILE_OR_DIR_LIST>` | Comma-separated list of locked files or directories |
| `<VALIDATION_TIER>` | no-test-needed / targeted-test / smoke-test / browser-test / full-suite / production-replay |
| `<VALIDATION_RESULT>` | pass / partial / fail / not_run |
| `<TRUST_LEVEL>` | self_claim / referenced / reproduced / independent_reviewed / blocked_or_suspicious |
| `<GO_PARTIAL_OR_RED>` | GO / PARTIAL / RED |
| `<COMMAND_LEVEL>` | none / read_only / tests_only / bounded |
| `<YES_OR_NO>` | yes or no |
| `<YES_OR_NO_OR_ASK>` | yes / no / ask |
| `<YYYY-MM-DD>` | ISO 8601 date |
| `<SCORE_0_TO_14>` | Integer 0-14 |
| `<NEXT_ACTION>` | Coordinator-owned state (wait_for_report / coordinator_review / needs_fix_task / close_task / blocked / assign_worker) |
| `<LOCK_STATUS>` | ACTIVE / RELEASED / BLOCKED / STALE / SUPERSEDED |
| `<STATUS>` | Task lifecycle status (DRAFT / ASSIGNED / RUNNING / REPORTED / REVIEWING / NEEDS_FIX / CLOSED_GO / CLOSED_PARTIAL / CLOSED_RED / BLOCKED / CANCELLED / SUPERSEDED) |

## Template Validation

To validate template files without failing on placeholder values:

```powershell
python -B scripts\validate-agent-inbox.py --template-mode templates
```

Template mode relaxes checks that require real values (dates, cross-file references, coordinator authority logic) while still validating schema structure, required fields, and format correctness.

## Private Data Rules

- Never put real agent names, model names, project paths, or secrets into `templates/`.
- Private concrete values belong only in installed local profile files or project-local `.agent-inbox/` files.
- The public safety scanner (`scripts/check-public-safety.py`) enforces this boundary.
- **Secrets never enter inbox, task, or report files.** Tokens, API keys, cookies, private account data, real paths under `C:\Users\<name>\` or `$HOME`, and similar sensitive values live in environment variables or local env files (`.env`, shell rc). The handoff copy-paste line, the task body, the report, the events log, and the `WORKTREE_LOCKS.md` `worktree_path` column are all sensitive surfaces — keep them clean. If a value must be referenced in a task or report, use a placeholder like `<env:NAME>` and document the expected env var in `AGENT_ROSTER.md` or the project's local profile file.
