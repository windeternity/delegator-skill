# Architecture Overview

This page maps how the pieces of Delegator fit together. For step-by-step setup, see [QUICKSTART.md](QUICKSTART.md). For the recommended operating model, see [CODEX_FIRST_OPERATING_MODEL.md](CODEX_FIRST_OPERATING_MODEL.md).

## Five concepts in one diagram

```text
┌─────────────────────────────────────────────────────────────┐
│  Delegator  (public skill / product name)                   │
│  └─ installed on the coordinator (e.g. Codex)               │
├─────────────────────────────────────────────────────────────┤
│  agent-file-coordination/*  (schema namespace)              │
│  ├─ task / report / roster / status-board                   │
│  ├─ worktree-locks / coordinator-verdict / event            │
│  └─ stable identifiers for compatibility                    │
├─────────────────────────────────────────────────────────────┤
│  scripts/  ── optional helpers                              │
│  ├─ afc-init                 bootstrap .agent-inbox/        │
│  ├─ afc-assign               generate task + handoff        │
│  ├─ afc-status               regenerate status board        │
│  ├─ afc-poll                 detect reports + next actions  │
│  ├─ validate-agent-inbox.py  validate coordination files    │
│  └─ summarize-codex-usage.py summarize coordinator usage    │
│  *Runtime-optional: the protocol works with plain files.*   │
├─────────────────────────────────────────────────────────────┤
│  templates/  ── placeholder artifacts                       │
│  └─ hydrate a project’s .agent-inbox/ (roster, locks, ...)  │
├─────────────────────────────────────────────────────────────┤
│  references/worker-brief.md  ── minimal brief               │
│  └─ for task-only workers that do not need the full skill   │
└─────────────────────────────────────────────────────────────┘
```

## Roles and evidence flow

1. **Coordinator** (e.g. Codex with full Delegator skill)  
   - Decomposes work, writes task files, maintains roster/status/locks.  
   - Gives the user one short handoff line per worker.  
   - Reviews reports as **untrusted evidence**, checks diffs/logs/screenshots, and issues a final `GO / PARTIAL / RED` verdict.

2. **Worker** (any agent that can read a task file and write a report)  
   - Executes only the assigned task inside its `Permission Scope`.  
   - Writes a structured report file; does not create tasks, reassign work, or approve final verdicts.

3. **Human owner**  
   - Sets goals, approves high-risk actions, and receives the coordinator’s final verdict.

## What each layer is (and is not)

| Layer | What it is | What it is not |
| --- | --- | --- |
| **Delegator** | The public skill name you install on the coordinator. | Not an agent runtime; it does not execute code by itself. |
| **agent-file-coordination/*** | The file schema namespace (task, report, roster, status-board, worktree-locks, coordinator-verdict, event). Kept stable for compatibility with existing templates, validators, and fixtures. | Not a separate product name. |
| **scripts/** | Optional helper scripts for init, assign, status, polling, validation, and usage summaries. | Not required; the protocol works with manual copy-paste and plain files. |
| **templates/** | Placeholder-driven template files to hydrate a project’s `.agent-inbox/`. | Not filled-in project files; placeholders must be replaced per project. |
| **references/worker-brief.md** | A lightweight prompt/context for agents that only need task execution guidance. | Not the full coordinator skill; workers should not get coordinator authority by default. |

## File conventions

- **Task file** — `.agent-inbox/task-<AGENT_NAME>-<task-id>.md`  
  Defines agent, role, permission scope, workspace mode, acceptance criteria, and report path.
- **Report file** — path specified by the task's `report_path` field, commonly `.agent-inbox/report-<AGENT_NAME>-<task-id>.md`  
  Worker output with verdict, changed files, evidence refs, trust level, and guardrail confirmation.
- **Status board** — `.agent-inbox/STATUS.md`  
  Coordinator-owned view of current tasks and next actions.
- **Worktree locks** — `.agent-inbox/WORKTREE_LOCKS.md`  
  Prevents parallel-edit conflicts by tracking which agent owns which file area.
- **Event log** — `.agent-inbox/events.jsonl`  
  Append-only log of state transitions (not for secrets or raw report content).

## Compatibility note

Delegator is the public skill name. The underlying protocol continues to use the `agent-file-coordination/*` schema namespace and `afc-*` script names so existing templates, validators, and early-adopter inboxes remain valid.

## Anti-Weight Principle

Delegator matures by reducing coordinator burden, not expanding it. Every change should either remove coordinator decisions, collapse repeated reads, or move complexity behind an optional helper. The full anti-weight governance rules are documented in `docs/QUALITY_ECONOMICS.md`.
