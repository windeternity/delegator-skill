# Delegator Skill

[![Validation](https://github.com/windeternity/delegator-skill/actions/workflows/validation.yml/badge.svg)](https://github.com/windeternity/delegator-skill/actions/workflows/validation.yml)

[中文说明](README.zh-CN.md)

**Local-file MOA coordination: bounded evidence, coordinator-owned verdicts.**

Delegator is a local-file MOA coordination protocol: workers produce bounded evidence inside explicit permission boundaries, and the coordinator keeps the final `GO / PARTIAL / RED` call. For semantic risk, protocol design, or competing patches, multiple workers review the same decision surface independently and synthesis compares evidence instead of counting votes. It also helps you avoid spending your strongest or most expensive coding agent on every implementation loop.

## Who this is for

Delegator is useful when you have more than one model, agent, or coding execution tool. Its purpose is not to make the most expensive or strongest model do everything from start to finish. It is the opposite: use the strongest model as the coordinator, and delegate clear, bounded, verifiable tasks to other workers.

A typical workflow looks like this: use Codex or another high-trust agent for decomposition, supervision, and final review, while assigning local implementation, testing, review, documentation, or smoke-test work to models such as GLM, MiniMax, DeepSeek, Qwen, or local models, running through tools such as OpenCode, Cline-style agents, Claude Code in third-party or bridge-based setups, IDE agents, or other project-specific workers.

These concrete names are examples, not recommendations, endorsements, or fixed routing rules. Model quality, pricing, tool permissions, and provider stability change quickly, so Delegator cares more about the current project roster, permission boundaries, and smoke-test evidence than any static model ranking.

Use it when multi-agent coding starts to look like this:

- you copy the same context into several agent chats;
- you lose track of who owns which task;
- a worker says "done" but the evidence is buried in chat history;
- Codex or another strong model burns quota reading code, editing, testing, fixing, and explaining every loop;
- workers can accidentally change files, run commands, or claim authority they were never given.

Delegator turns that into a local task-file workflow:

```text
User goal
  ↓
Coordinator splits work into task files
  ↓
Workers execute only their assigned scope
  ↓
Workers write structured reports
  ↓
Coordinator checks evidence and decides GO / PARTIAL / RED
```

It is most useful for complex, parallel, evidence-heavy work where a strong coordinator should supervise and judge while cheaper or better-suited workers handle implementation, testing, review, or bulk checks.

## Why Delegator is different

- **Workers install nothing.** Only the coordinator carries the skill; each worker gets one task file and one copy-paste instruction.
- **Reports are evidence, not authority.** Workers cannot approve themselves, expand scope, or overrule the task file.
- **Permissions are explicit.** Read, edit, run, network, commit/push, and destructive actions are declared in the task file.
- **Verdicts are scored.** A 14-point rubric across seven axes backs every `GO / PARTIAL / RED`.
- **State lives in files.** Tasks, reports, status boards, event logs, locks, and verdicts are reviewable, diffable, and reproducible.
- **Runtime-optional.** Helper scripts reduce manual work, but Delegator still works as plain local files.
- **Quota-aware for complex tasks.** Keep Codex or another strong model focused on decomposition, supervision, evidence review, and final judgment; move long execution loops to cheaper or specialized workers.
- **Deny by default.** Commit/push is never pre-approved, destructive actions are always off, and a task file outranks anything a report says.

## When not to use it

Do not use Delegator for tiny one-shot edits where the coordinator can finish faster than it can delegate. Writing a task file, reading a report, and issuing a verdict all have overhead. Delegator pays off when work is complex, parallel, risky, evidence-heavy, or suitable for cheaper/specialized workers.

The current release enforces this with an early route gate. Work below four
estimated direct hours stays `DIRECT` unless it has real independent
parallelism, needs an unavailable capability, or warrants independent
high-risk review. The gate runs before roster, template, or inbox reads. A
narrow no-inbox `LITE` path exists when the user explicitly requires one
external worker for low-risk non-semantic work.

## How it works

```
 Coordinator                .agent-inbox/               Worker
 ──────────                 ─────────────               ──────
 Write task file  ────────► task-Reviewer-*.md
 Read report      ◄──────── report-Reviewer-*.md   ◄─── Read task, work inside
 Score verdict                                      │    assigned scope, write
                                                    │    structured report
 Write task file  ────────► task-Implementer-*.md   │
 Read report      ◄──────── report-Implementer-*.md ◄───
 Score GO / PARTIAL / RED
```

Each task file is a self-contained contract — assigned agent, permission scope, guardrails, acceptance criteria, and report path:

```yaml
# .agent-inbox/task-Reviewer-guardrail-audit.md
---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: demo-reviewer-guardrail-audit
agent_name: Reviewer
permission_scope:
  read_files: yes
  modify_source: no
  run_commands: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: read_only_shared
validation_tier: no-test-needed
report_path: .agent-inbox/report-Reviewer-guardrail-audit.md
---
```

The coordinator reads the report back, checks evidence, and issues a scored verdict — not a vibe check, but a 14-point rubric across seven axes: scope, evidence, validation, safety, reproducibility, conflict awareness, and prompt-injection resistance.

## Install and smoke-test

### Coordinator (required)

Clone or download this repository, then copy it into your Codex skills directory as `delegator`:

```powershell
git clone https://github.com/windeternity/delegator-skill.git
$dest = "$env:USERPROFILE\.codex\skills\delegator"
New-Item -ItemType Directory -Path $dest -Force | Out-Null
Get-ChildItem .\delegator-skill -Force |
  Where-Object { $_.Name -notin @(".git", ".github", ".claude", ".codex", ".agent-inbox") } |
  Copy-Item -Destination $dest -Recurse -Force
```

On macOS/Linux:

```bash
git clone https://github.com/windeternity/delegator-skill.git
mkdir -p ~/.codex/skills
rsync -a --delete \
  --exclude='.git' \
  --exclude='.github' \
  --exclude='.claude' \
  --exclude='.codex' \
  --exclude='.agent-inbox' \
  delegator-skill/ ~/.codex/skills/delegator/
```

For other coordinator platforms that support custom skills, prompts, or context directories, copy `SKILL.md`, `references/`, and `docs/CODEX_FIRST_OPERATING_MODEL.md` into that platform's supported directory.

### Worker (nothing to install)

Workers only need their task file and one copy-paste line:

```text
Read <task-file-path>. Confirm you are <Agent Name>. Execute only this task within its Permission Scope and write your report to the specified Report Path. Do not commit or push.
```

Optionally, give workers `references/worker-brief.md` for lightweight protocol context.

### Smoke test

After installing on Codex, ask:

```text
Use the Delegator skill. Create a demo two-agent plan for a read-only review and a small implementation task. Use neutral agent names, write task files under .agent-inbox/, include permission scope and report trust fields, and give me only the one-line copy-paste instruction for each agent.
```

A good result includes explicit `Agent Name`, `Permission Scope`, `Workspace Mode`, `Guardrails`, `Acceptance Criteria`, `Report Path`, report trust fields, and no hard-coded paths or vendor names.

On your **first delegation**, the agent interviews you once and saves your config (available workers/CLIs, model preferences, automation level) to the project-local roster, then reuses it. What it needs depends on your automation level — CAL-1/CAL-2 accept any worker you relay; CAL-3 requires a verified callable CLI. See [First Run](docs/FIRST_RUN.md).

### Validation

```powershell
python scripts/validate-agent-inbox.py examples/fixtures/valid     # good examples — PASS
python scripts/validate-agent-inbox.py examples/two-agent-demo      # demo — PASS
python scripts/validate-agent-inbox.py examples/moa-review-demo     # MOA review demo — PASS
python scripts/validate-agent-inbox.py examples/moa-synthesis-demo  # MOA synthesis demo — PASS
python scripts/validate-agent-inbox.py examples/fixtures/invalid    # bad examples — expected to FAIL
python scripts/check-public-safety.py .                             # scan for secrets/real paths
# Note: run against the exported/public package (or a clean snapshot). The
# private upstream checkout intentionally contains local coordination state
# (.agent-inbox, .learnings, …) and may fail public-safety checks even when
# the exported package is clean. Run the scanners against a clean, isolated
# copy of the package, not a working checkout that carries local state.
```

## Documentation

**Getting started**
- [First Run](docs/FIRST_RUN.md) — start here: what the agent asks you on first delegation, and how requirements differ by automation level
- [Quickstart](docs/QUICKSTART.md) — minimal setup and smoke test
- [Architecture](docs/ARCHITECTURE.md) — project structure, file roles, and data flow
- [Hydration Guide](docs/HYDRATION_GUIDE.md) — first-use template hydration flow

**Going deeper**
- [Positioning](docs/POSITIONING.md) — product boundary and MOA-first north star
- [When To Use AFC](docs/WHEN_TO_USE_AFC.md) — direct, LITE, FULL delegation, and MOA decision tree
- [Quality Economics](docs/QUALITY_ECONOMICS.md) — quality-adjusted coordination ROI
- [Benchmark Plan](docs/BENCHMARK_PLAN.md) — direct vs delegation vs MOA evidence template
- [Codex-First Operating Model](docs/CODEX_FIRST_OPERATING_MODEL.md) — recommended operating model
- [Cache Hygiene](docs/CACHE_HYGIENE.md) — prompt-cache optimisation for coordinators and workers
- [Worker Brief](references/worker-brief.md) — lightweight worker-side context

**Reference**
- [Task/Report Schema](references/task-report-schema.md) — schema for task, report, roster, status board, event log, worktree lock, and coordinator verdict files
- [MOA Coordination Modes](references/moa-coordination-modes.md) — `delegate_full`, `moa_review`, `moa_design`, `moa_patch`, and `moa_synthesis`
- [MOA Synthesis Rubric](references/moa-synthesis-rubric.md) — evidence-weighted comparison rules
- [Source Artifacts](references/source-artifacts.md) — upstream PRD, spec, issue, and report inputs
- [Assignment Quality Checklist](references/assignment-quality-checklist.md) — pre-dispatch task quality gate
- [Decision Rubric](references/decision-rubric.md) — 14-point scoring rubric for verdicts
- [Permission Matrix](references/action-permission-matrix.md) — default allow/deny for agent actions
- [Report Trust & Prompt Injection](references/report-trust-and-prompt-injection.md) — trust levels and injection handling

## Scope and boundaries

Delegator is a coordination protocol, not an agent runtime. It does not execute code, does not require any specific worker model or vendor, and does not publish benchmarks. It should not auto-commit, push, merge, delete branches, deploy, or expose private data unless the user explicitly authorizes that in the current project. Keep the reusable skill clean — do not commit generated inboxes, worktrees, reports, real project data, `.env` files, logs, or screenshots containing private data.

## Naming and compatibility

Delegator is the public skill name. The underlying file protocol currently uses the `agent-file-coordination/*` schema namespace and `afc-*` helper script names for compatibility with existing templates, validators, fixtures, and early adopters. These are stable protocol identifiers, not a separate product name.

## License

[MIT](LICENSE)
