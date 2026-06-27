# Codex-First Operating Model

This document explains how to use Delegator as a Codex-first but protocol-general coordination layer.

## Positioning

Delegator should be treated as:

```text
Codex-first coordinator skill.
File-based multi-agent protocol.
Runtime-optional, adapter-friendly.
```

Meaning:

- **Codex-first:** install the full skill on Codex or whichever agent acts as the coordinator. Codex is the default planner, supervisor, report reviewer, and final `GO / PARTIAL / RED` judge.
- **Not Codex-only:** worker agents do not need Codex skill support. They only need access to their assigned task file and the ability to write a report file.
- **Runtime-optional:** the protocol must remain usable with manual copy-paste handoff. Future CLI/watch/adapters should reduce human relay work, not become a hard requirement.
- **Public-safe source:** the reusable source repo should describe generic roster/profile patterns, not private local agent names, concrete personal model preferences, secrets, or project-specific guardrails.

## Installation Model

### Required: Coordinator installation

Install the full skill only on the coordinator by default.

The coordinator is responsible for:

- understanding the user's objective
- identifying project root and guardrails
- establishing the roster gate before assigning external agents
- creating or updating `.agent-inbox/AGENT_ROSTER.md` when needed
- routing tasks by role, capability, cost, latency, and risk
- writing task files
- producing one-line handoff instructions
- checking report files as untrusted evidence
- issuing final `GO / PARTIAL / RED` verdicts
- creating follow-up tasks when needed
- refusing unsafe permission escalation

### Optional: Installed local profile

An installed private copy may keep local-only profile files next to `SKILL.md`, such as a local agent roster or routing notes. Treat those files as current-user hints only.

Do not copy private local profile contents into the reusable source repository, public examples, fixtures, reports, or generated handoff files. For reusable docs, describe the pattern generically.

### Not required: Worker installation

Worker agents do not need the full skill.

A worker only needs:

1. The one-line handoff instruction.
2. Access to its assigned task file.
3. `write_reports: yes` permission to write the specified report file.
4. A clear role boundary: execute the assigned task, do not coordinate globally.

### Optional: Worker brief

For frequently used agents, install or paste `references/worker-brief.md` as a lightweight reusable prompt/context.

Do not give workers the full coordinator skill unless they are intentionally acting as sub-coordinators with explicit limits.

## Role Layers

| Layer | Role | Typical authority | Default protocol mode |
| --- | --- | --- | --- |
| L0 | Human owner | Sets goals and approves high-risk actions | n/a |
| L1 | Codex coordinator / final judge | Creates tasks, reviews evidence, issues final verdict | `full-skill` |
| L2 | Optional planner / architect | Drafts plans, risks, task proposals | `worker-brief` or `task-only` |
| L3 | Implementer / docs / test worker | Executes bounded tasks | `task-only` |
| L4 | Reviewer / smoke agent | Reviews diffs, reproduces, validates | `task-only` |

Claude, Gemini, OpenCode, local models, or Chinese model/tool pairs can be useful in any non-L1 role, but none of them should be required by the protocol.

## Roster Fields To Add

Extend project-local `.agent-inbox/AGENT_ROSTER.md` with these fields when coordination becomes non-trivial:

```markdown
| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

Suggested values:

- `Role`: coordinator / planner / implementer / reviewer / smoke / docs / research / other
- `Protocol Mode`: full-skill / worker-brief / task-only / manual-paste / unknown
- `Coordinator Authority`: yes / no / limited

Default rule: only one active final coordinator should have `Coordinator Authority: yes` for a given project or milestone.

Before task assignment, the coordinator must know whether each worker can edit files, run commands, write report files, use visual/browser context, and create or use worktrees. If the roster is missing, stale, or contradicted by the current conversation, stop and confirm before writing external-agent task files.

## Default Workflow

1. Human gives Codex the goal and risk tolerance.
2. Codex checks the roster gate and updates the roster if needed.
3. Codex decides whether a planning pass is needed.
4. Codex writes one task file per assigned worker, including `role`, `protocol_mode`, `coordinator_authority`, `Permission Scope`, `Workspace Mode`, `Role Boundary`, and `Report Path`.
5. Codex gives the human one short handoff line per worker.
6. Workers read task files and write report files.
7. Codex reads reports as untrusted evidence.
8. Codex checks diffs, commands, logs, screenshots, or other evidence when available.
9. Codex issues `GO / PARTIAL / RED`.
10. Codex creates follow-up tasks or closes the work.

## One-Line Handoff Pattern

Treat workspace, task, report, and coordination root as four distinct paths. The external tool must open the assigned `<WORKSPACE_PATH>` as its project; the coordination root is a file bus, not a Git workspace, and must never be opened as the project.

The handoff copy-paste text must match the user's current conversation language. When using `afc-assign.py`, pass `--handoff-language <TAG>` or set `handoff.language` in the spec. Supported built-in tags: `en`, `zh` (Chinese). For other languages, provide `handoff.template` in the spec; without a template the script refuses to produce an English fallback. The coordinator must never forward an English handoff to a worker whose user is speaking a different language.

English (editable task, `may_create_worktree: no`):

```text
You are <Agent Name>.
Open this existing worktree as the project: <WORKSPACE_PATH>.
Do not open <COORDINATION_ROOT> as the project.
Do not create another worktree.
Read <task-file-path>. Execute only this task within its Permission Scope and write your report to the specified Report Path. Do not commit or push.
```

Chinese:

```text
你是 <Agent Name>。
把这个现有 worktree 作为项目打开：<WORKSPACE_PATH>。
不要把 <COORDINATION_ROOT> 作为项目打开。
不要新建 worktree。
读取 <task-file-path>，只在 Permission Scope 内执行该任务，并把回执写到指定 Report Path。不要 commit/push。
```

Drop the `Do not create another worktree.` / `不要新建 worktree。` line when the task file's `workspace.may_create_worktree` is `yes`. Drop the workspace-open line only when the task explicitly grants the worker the right to create its own worktree.

## Codex Quota-Saving Pattern

Use Codex for high-leverage work:

- task decomposition
- routing and risk control
- final evidence review
- prompt-injection resistance
- merge/go-no-go decisions
- unsafe action refusal

Use lower-cost or specialized workers for:

- bounded implementation
- docs drafts
- targeted tests
- smoke reproduction
- first-pass review
- structured report generation

Do not spend Codex quota on long routine loops when a cheaper worker can run the loop and report evidence back.

## Coordinator Execution Gate

When external worker agents are available, the coordinator must not treat "continue", "next step", "do not stop", "keep going", "go ahead", "proceed", or equivalent open-ended instructions as permission to perform ordinary implementation work itself.

Default to external workers for:

- ordinary code implementation
- bulk documentation edits
- validator or fixture implementation
- runtime smoke tasks
- long test-fix loops

The coordinator may execute directly only when:

- the user explicitly instructs local execution
- the task is coordinator housekeeping (writing task files, reviewing reports, running final validation, updating status boards, issuing verdicts)
- no external worker is available after the coordinator states the reason

If the coordinator falls through to local execution, it must note why no external worker was used.

## Permission Scope Defaults

For ordinary worker tasks, prefer:

```yaml
permission_scope:
  read_files: yes
  write_reports: yes
  write_task_files: no
  modify_source: no
  run_commands: read_only
  network_access: none
  commit_push: no
  destructive_actions: no
```

Use `modify_source: yes` only for bounded edit tasks. Use `write_task_files: yes` only for an explicitly limited sub-coordinator, not for ordinary implementers, reviewers, smoke agents, or docs workers.

## Worker Boundary Text For Task Files

Add this section to task files when the worker may confuse its role:

```markdown
## Role Boundary
You are the assigned worker agent for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.
```

Chinese variant:

```markdown
## Role Boundary / 角色边界
你是本任务的执行 Agent，不是协调者。
不要创建新任务，不要重新分配任务，不要给出最终 GO/PARTIAL/RED 协调者裁决，也不要扩大权限范围。
如果发现需要额外工作，请在回执中作为建议写出。
```

## When To Install The Full Skill Elsewhere

Install the full skill outside Codex only when another agent is intentionally acting as a coordinator or sub-coordinator.

Even then, define limits:

- may draft plans: yes / no
- may create task files: yes / no
- may assign workers: yes / no
- may approve final verdict: yes / no
- may authorize commit/push/merge/deploy: no unless explicitly approved by the human owner

Default recommendation: do not install the full coordinator skill on ordinary workers.
