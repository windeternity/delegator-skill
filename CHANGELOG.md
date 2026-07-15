# Changelog

All notable changes to Delegator will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-07-15

### Added

- Install-local `LOCAL_ROSTER.md` defaults, deterministic roster resolution,
  and a reusable local-roster template for first-use configuration.
- A scenario-first Minimal Loop guide plus six public benchmark cases covering
  direct, LITE, FULL, MOA review, delegation-loss, and CAL-boundary decisions.
- Shared AFC constants and expanded fixtures for routing, roster resolution,
  lifecycle handling, synchronization boundaries, and public contracts.

### Changed

- First-use routing now fails closed on built-in/current-session subagent
  aliases and keeps Delegator focused on explicitly rostered external workers.
- CAL-3 remains opt-in while adding clearer network/work/approved-commit
  permission profiles, stronger worker binding, and safer launcher behavior.
- Coordinator entry points, help output, task generation, snapshot guidance,
  and public documentation now share the same route-first operating contract.

### Fixed

- CAL-3 heartbeat, abort, timeout, retry, and attempt history now use canonical
  append-only events instead of losing audit evidence across successful retry.
- Assignment sequence locks recover abandoned owners safely on Windows and
  POSIX while preserving concurrent uniqueness and live-owner locks.
- Private/public CI now validates the correct safety surface and skips
  source-only maintenance fixtures when they are absent from the public package.

### Security

- GitHub Actions are pinned to immutable SHAs, CI permissions remain
  `contents: read`, and the public export continues to exclude local state,
  private review material, maintenance scripts, and public-owned release history.

## [0.3.0] - 2026-06-27

### Added

- `scripts/afc-repair-report.py` — coordinator-side repair tool for a rejected
  worker report, closing the CAL-2 schema-reject gap. When a worker writes an
  invalid report and its process has exited (common in CAL-2 relay mode), the
  watcher emits `report_rejected` (exit 3) and nothing re-dispatches the task.
  This tool diagnoses the rejection and, for the recurring unambiguous schema
  mistakes (`trust_level: verified` → `referenced`, `verdict: CLOSED_GO` → `GO`,
  `validation.result: passed` → `pass`, `validation.tier: full_suite` →
  `full-suite`), applies a one-line frontmatter fix. Default is dry-run;
  `--write` persists via atomic temp + replace. It never edits the report body
  (the worker's evidence and verdict rationale stay intact), backfills missing
  guardrail fields only with safe defaults, and refuses dangerous-phrase or
  over-budget reports even with `--write`. Includes
  `examples/fixtures/afc-repair-report/` (38 checks) wired into CI.
- K5 risk-weighted verification guidance: task-shape evidence remains the hard
  floor, risk raises depth only where needed, equivalent surfaces share one
  bounded validation plan, and no new schema fields are introduced.
- `scripts/afc-route.py` / `afc_routing.py` — binding pre-coordination ROI gate
  returning DIRECT, LITE, FULL, SPLIT, or INVALID with deterministic thresholds.
- `scripts/afc-lite.py` — no-inbox compact handoff for explicitly required,
  low-risk, non-semantic single-worker tasks.
- `scripts/afc-report.py` — compact schema-valid worker report generator with
  legal enums, task cross-checks, and a 3 KB hard budget.
- `scripts/afc-intake.py` — one-call batch intake for report validation, size,
  Git branch/base, changed paths, and locked scope.
- `examples/fixtures/afc-efficiency/` — 75 regression checks for route truth
  tables, hard budgets, LITE behavior, report generation, and batch intake.
- `references/delegation-routing-v1.md` — active routing contract for the
  DIRECT/LITE/FULL/SPLIT decision.
- `references/coordinator-scan-routing.md` — defines the coordinator scan-routing rule: prefer snapshots/summaries or bounded read-only exploration packets instead of broad source scans in the coordinator thread.
- `scripts/afc-handoff.py` — generates a compact new-thread handoff (roster, active tasks, recent events, blockers, next action, guardrails) from existing `.agent-inbox/` state, so changing an overgrown coordinator thread costs one command instead of a hand-written summary. Read-only by default; `--write` saves `<INBOX>/NEW_THREAD_HANDOFF_<DATE>.md`. Fails closed on malformed/duplicate/orphan inbox state. Stdlib only, Windows + POSIX safe, deterministic with `--date`. Ships `examples/fixtures/afc-handoff/` (12-test runner) and is wired into CI.
- `scripts/afc-next.py --context-pct <N>` — optional coordinator thread-pressure override that turns the advisory `>50%` compact / `>80%` handoff rules (docs/CACHE_HYGIENE.md) into a deterministic verdict. At/above `--handoff-pct` (default 80) the action becomes `RECOMMEND_HANDOFF`, preempting every inbox action except `FAIL`; in the `--compact-pct` (default 50) band it adds an `advisory` line. Self-reported only — without the flag the output is byte-identical to the prior inbox-only behavior. Adds 8 fixture tests; the afc-next runner is now wired into CI.
- `scripts/afc-watch.py --auto-archive` — opt-in CAL-2 lifecycle housekeeping that archives at most one validated coordinator-closed task/report set per watcher invocation, refreshes `STATUS.md`, and fails closed on missing reports or invalid inbox state without selecting verdicts or launching workers.
- `scripts/afc-cal3-probe.py`, `scripts/afc-cal3-dispatch.py`, and
  `scripts/afc-release-executor.py` — opt-in C6/CAL-3 worker-dispatch
  foundation. The probe creates project-local invoke recipe drafts, the
  dispatcher launches headless CLI workers with argv-only commands, per-task
  logs, visible status lines, and CAL-2 watcher intake, and the release
  executor performs deterministic post-GO commit/push chores behind hard
  gates. The dispatcher includes a default two-attempt rework fuse and the
  release executor enforces explicit push approval. Local recipes and artifacts
  stay under `.agent-inbox/` and are not part of the public skill package.
  Includes `examples/fixtures/afc-cal3/` coverage wired into CI.
- `examples/fixtures/e2e-dogfood/` — minimal end-to-end dogfood fixture covering init → assign → report → status → poll → verdict → usage summary → cross-check validation. Proves the smallest closed loop of the agent-file-coordination protocol is not broken. 24 checks across 9 stages, all in a temporary directory with deterministic dates.
- `examples/fixtures/codex-usage/run-tests.py` — 12-test fixture runner for `summarize-codex-usage.py` covering single/two-label aggregation, JSON output, Desktop `token_count` cumulative snapshots, nested `turn.completed`, canonical-vs-fallback `cached_input_tokens`, real Codex log parsing, malformed JSON / no-usage-event negative paths, `--require-label` pass/fail, and malformed CLI arguments. Closes the `summarize-codex-usage.py` CI coverage gap.

### Changed

- `audit-docs.py` adds an advisory surface-area growth gate: it counts
  `scripts/*.py` and `references/*.md` and prints a `WARN` (never an error,
  never changing the exit code) when either exceeds its `*_COUNT_WARN` budget
  (40 each), so installed-weight creep is visible before it compounds. Silent
  unless run at the repo root. `examples/fixtures/audit-docs-growth/` covers
  under/over threshold and is wired into CI.
- `SKILL.md` size gate is now two-tier in `audit-docs.py`: `SKILL_SIZE_TARGET`
  (8000 bytes, soft) and `SKILL_SIZE_HARD` (9000 bytes, hard ceiling). At/below
  the target the gate is clean; in the `8000 < size <= 9000` tolerance band it
  passes with an advisory `WARN` so a small edit no longer forces a byte-shaving
  commit; above the hard ceiling CI still fails. Both values may only ratchet
  down. `examples/fixtures/audit-docs-size/` now covers all three tiers.
- `recommend_cal()` in `afc-first-run-config.py` now matches CAL indicators on
  word boundaries via explicit per-CAL keyword sets (`CAL2_INDICATORS`,
  `CAL3_INDICATORS`) instead of bare substring `in` checks, so `cli` no longer
  matches inside `client` and a multi-word phrase like `auto intake` is matched
  as a unit rather than via a bare `auto`. Priority is unchanged (CAL-2 watcher
  > CAL-3 CLI > CAL-1 default) and explicit. Adds substring-trap and
  priority regression tests to `examples/fixtures/afc-first-run/`.
- The watcher (`afc-watch.py`) now runs the same task cross-checks intake does.
  Its report validation loads the matching task's frontmatter and passes it to
  `validate_report_schema`, so a report whose `agent_name`, `coordination_mode`,
  or `comparison_group` does not match its task is rejected at the watcher
  (exit 3) instead of being silently accepted and only failing later at intake.
  Previously the watcher validated report schema in isolation, which could let a
  report pass the watcher but be rejected by `afc-intake.py`. `afc_inbox_validation.validate_report`
  now evaluates guardrail/evidence-trust booleans with the same `bool_enabled`
  semantics (true/yes/approved) as the shared `afc_validation` core, so a
  frontmatter value like `commit_push_done: yes` is caught identically on both
  paths.
- Coordination budget raised from 2 KB to 4 KB. `TASK_BUDGET_BYTES` (generated
  task file size, enforced by `afc-assign.py` and surfaced as advisory warnings
  by `afc-poll.py`/`afc-snapshot.py`/`afc-status.py`) and `MAX_FULL_CONTEXT_BYTES`
  (the routing inline-context `SPLIT` gate in `afc_routing.py`) both move from
  `2 * 1024` to `4 * 1024`. The two are independent constants that previously
  shared a value; they move together so the router gate (which runs before task
  generation) and the post-generation size guard stay consistent. 4 KB matches
  the real shape of refined review/verification tasks, which carry field
  checklists, and keeps tasks above the 3 KB ordinary-report budget. Companion
  convention documented in `docs/CACHE_HYGIENE.md`: coordinator-created briefs,
  specs, and scratch notes must live under `.agent-inbox/` (not the workspace
  root), where they are gitignored and excluded from out-of-scope checks and do
  not count toward the task-file budget; point to them from the task's
  `read_first`.
- First-use bootstrap now treats execution-model preference and CAL-1/CAL-2
  selection as recorded project-local defaults: the coordinator asks when no
  preference exists, writes the answer to the roster/events, and reuses it until
  the user asks to change it.
- `afc-assign.py` requires `routing.*` evidence for new assignments, accepts
  only FULL routes, records the route, and enforces a 2 KB generated-task budget.
- `SKILL.md` is now a 5.7 KB route-first entrypoint. FULL-only procedure moved
  to `references/full-coordination-protocol.md`; the root size gate ratcheted
  from 21 KB to 8 KB so DIRECT/LITE do not carry the full protocol.
- Task/report templates are compact enough to match the documented 2 KB/3 KB
  budgets; LITE mode is active as a narrow no-inbox exception.
- `afc-report.py` binds output to the task-declared `report_path`, scans the
  complete report body, and uses collision-safe atomic replacement.
- `afc-assign.py` embeds the local report-generator path in generated tasks;
  validator enum failures now list allowed values for one-shot worker fixes.
- `afc-intake.py --task-id` validates only the selected batch contracts, so
  unrelated historical inbox artifacts cannot force a repair round. Git status
  parsing now preserves tracked paths exactly.
- `SKILL.md` — slimmed dispatch/workspace gate prose while adding a one-line Coordinator Execution Gate pointer for scan routing, keeping the root skill under its 21,000-byte audit ceiling.
- `README.md` / `README.zh-CN.md` — sharpened the public landing-page positioning around Codex/main-model quota pressure, coordinator-as-control-desk workflow, worker task files, evidence review, and when not to delegate tiny tasks.
- Renamed the public skill from `agent-file-coordination` to Delegator while retaining the `agent-file-coordination/*` schema namespace for compatibility.
- `.github/workflows/validation.yml` — fixed branch trigger to fire on both `main` and `master` pushes (previously only `main`, so direct pushes to the actual `master` branch were not running CI). Added 5 new CI steps wiring the existing fixture runners to CI: `afc-init` (34 checks), `afc-assign` (17), `afc-status` (8), `afc-poll` (6), and the new `summarize-codex-usage` (12). Brings total CI fixture coverage to 91 checks.

### Fixed

- `afc-route.py` no longer invents a large smallest-workstream estimate when a
  multi-stream caller omits that evidence; uncertain parallel work stays direct.
- FULL assignment and report generation now reject report paths outside the
  assigned inbox, and generated worktree commands quote paths with spaces.
- `afc-assign.py` no longer repeats `report_path` in generated task bodies,
  keeping release-operator tasks inside the 2 KB hard budget while preserving
  the frontmatter contract.
- Corrected the same-task batch-cost schema diagnosis: existing validators already accept
  case-normalized `PASS`; the real invalid value was `trust_level: high`.
- `examples/fixtures/afc-assign/run-tests.py` — isolates the attribution-absent fixture from ambient `CODEX_THREAD_ID` / `CODEX_ROOT_THREAD_ID` environment variables so local Codex runs match clean CI behavior.
- `examples/fixtures/afc-init/run-tests.py` — cross-platform `bash` / `pwsh` shell detection so the runner works under Ubuntu CI as well as Windows; fixed a `NoneType` skip path that broke when one of the two shells was unavailable.

## [0.2.0] - 2026-06-09

### Added

- `scripts/afc-poll.py` and `examples/fixtures/afc-poll/` — C1 polling helper: runs `afc-status.py` once, compares report file mtimes against `<INBOX_DIR>/.afc-poll-state.json`, and prints a coordinator-oriented `next_action` list (text or JSON). Standard library only, Python 3.8+, Windows + POSIX safe. Atomic state update, honors `--dry-run`. Fixture coverage: fresh-inbox, second-run (with deterministic state reset for idempotency), dry-run, missing-inbox; 6-test runner under `examples/fixtures/afc-poll/run-tests.py`.
- `scripts/afc-init.ps1`, `scripts/afc-init.sh`, and `examples/fixtures/afc-init/` — added platform-native inbox bootstrap scripts that create `.agent-inbox/AGENT_ROSTER.md`, `STATUS.md`, `WORKTREE_LOCKS.md`, and `events.jsonl` from templates with overwrite protection, deterministic date input, and cross-shell fixture coverage.
- `scripts/afc-assign.py` and `examples/fixtures/afc-assign/` — added a standard-library task generator that reads a short spec, emits a schema-valid task file, appends a `TASK_ASSIGNED` event, prints worker handoff text with identity/workspace gates, and ships generation/failure fixtures.
- `scripts/afc-assign.py` — language-aware handoff generation: `--handoff-language <TAG>` CLI flag and `handoff.language` spec field, with CLI overriding spec; built-in support for English (`en`) and Chinese (`zh`); for unsupported languages, requires `handoff.template` in spec with variable substitution (`{agent_name}`, `{ws_path}`, `{inbox_dir}`, `{task_filepath}`, `{report_path}`), otherwise exits with error — no silent English fallback; backward-compatible default to English.
- `scripts/afc-status.py` and `examples/fixtures/afc-status/` — added a standard-library status-board generator that scans task/report frontmatter, regenerates schema-valid `STATUS.md`, appends `STATUS_UPDATED` events, and ships success/failure fixtures with a local fixture runner.
