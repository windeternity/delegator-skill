# Cache Hygiene Guidance

This document defines cache-hygiene practices for Delegator. The goal is to maximise prompt-cache hit ratio for both the coordinator and workers by making cache-friendly layout an explicit protocol concern, not an operator discipline assumption.

---

## Stable-Before-Dynamic Prompt Layout

Prompt-cache systems (Codex, Claude, and others) reuse previously-seen input-token prefixes. The longer the shared prefix, the higher the cache savings. This principle has one clear implication for protocol artifacts:

**Place stable content before dynamic content in every file that an agent reads.**

| Layer | Content | Stability |
|---|---|---|
| 1 | YAML frontmatter (schema, schema_version, task_id) | Most stable |
| 2 | Role boundary, permission scope, guardrails | Stable per task |
| 3 | Purpose, acceptance criteria | Stable per task |
| 4 | Findings, evidence, changed files | Dynamic per report |

Reorder only when the task explicitly requires it. The default template order already follows this pattern; do not insert dynamic sections before stable ones.

---

## Coordinator Cache Rules

1. **Read the skill body once per session.** The skill body is the largest fixed per-turn input cost. After the first turn, it should be fully cached. Do not trigger a re-read by changing the skill body mid-session.
2. **Read the roster once.** Cache the roster after the first read. Do not re-read on every turn.
3. **Read task files only when assigning or reviewing.** Do not re-read task files on every coordinator turn. For routine state checks, use `scripts/afc-snapshot.py --brief` or `scripts/afc-status.py --summary-only`.
4. **Keep handoffs short.** The handoff copy-paste instruction is a fixed-cost input for the worker. One line is enough. Do not expand it with task context that already exists in the task file.
5. **Keep verdicts compact.** Score breakdown + evidence paths + blockers. Do not restate the task or echo the full report body (anti-patterns #1 and #2).
6. **Prefer file references over inline content.** Reference `changed_files` paths instead of reading full diffs. Reference the report path instead of copying the report body into the verdict.
7. **Retire long coordinator threads.** At >50% context, compress before continuing. At >80%, write a new-thread handoff. At >100 tool calls, review the cost pattern; at >500, stop expanding scope and close or hand off.
8. **Read budget — each artifact *version* at most once per session.** Do not re-read what is already recorded or already consumed at the same version. Specifically: the skill body is read once (rule 1); the roster once (rule 2); each reference document once, when its route fires, never pre-emptively; each task file only when assigning or reviewing it (rule 3); each report once *per version* — the `.afc-poll-state.json` seen-state and `append_event_once` idempotency key on the report's mtime, so a consumed report is not re-counted, but a newer mtime on the same `report_path` (a resubmitted repair report) is a new version and must be re-read and re-reviewed. The first-run CAL preference is read once via a presence check on `.agent-inbox/AGENT_ROSTER.md`; if a CAL default is recorded, skip the init interview entirely rather than re-asking. For routine state, prefer `scripts/afc-snapshot.py --brief` or `scripts/afc-status.py --summary-only` over re-reading full files.

---

## Worker Cache Rules

1. **Read the task file first, once.** The task file becomes cached input for the rest of the session.
2. **Write the report in template order.** Frontmatter first, then verdict, then sections in template order. The coordinator reads reports in this order; keeping the layout stable maximises the coordinator's cache hits during report intake.
3. **Keep reports concise.** This is the single most impactful worker-side lever for coordinator cache hygiene. See Report Compression below.

---

## Worker Session Affinity

Provider caches are prefix caches over a session's conversation history. A worker that already read the repo holds that context as a cached prefix; a fresh worker re-derives the same context at full price through new tool calls. Worker selection is therefore a cache decision, not only a capability decision.

**Rules:**

1. **Within one work burst, route related sequential tasks to the same worker session.** The follow-up task appends to an already-cached prefix instead of paying context ramp-up again.
2. **Keep the worker's model fixed for the life of the session.** Caches are model-scoped; switching models mid-session rebuilds the cache from zero. A task that needs a different model is a new worker session with its own ramp-up cost.
3. **Affinity governs sequential work, not parallel work.** Independent tasks still go to different workers for wall-clock throughput; affinity decides who gets the *next* task in the same area.
4. **Reset instead of reuse when the session is contaminated.** Repeated failed attempts, a large abandoned approach, or an area switch make the accumulated context a liability. Cache savings never justify continuing a poisoned session — start fresh and pay the ramp-up.
5. **After a long idle gap, decide on relevance, not cache.** Past the provider TTL the cache is cold either way. Continue the session only if its accumulated context is still the right context for the next task.

Practical default: one worker session per project area per work burst, reset at task-closure milestones.

---

## Cache Windows and Burst Scheduling

Prompt caches expire on the order of minutes, so *when* dialogue happens matters as much as *what* it contains.

| Provider (as of 2026-06) | Mechanism | Typical TTL | Cached-input cost |
|---|---|---|---|
| Anthropic API | explicit `cache_control` breakpoints | 5 min default, optional 1 h | ~0.1× input (writes 1.25× / 2×) |
| OpenAI / Codex | automatic prefix caching | minutes-scale | model-dependent, down to ~0.1× |
| Subscription CLI workers | provider-managed, opaque | unknown | latency and provider-load benefit; billing not directly visible |

**Rules:**

1. **Batch the dialogue with one worker.** `assign → report → follow-up` exchanges with the same worker should run back-to-back. Interleaving several workers' dialogues stretches each one past the TTL and turns every resumed turn into a cache miss.
2. **Expect cold starts after gaps.** Overnight or multi-hour gaps always start cold. Do not contort the workflow to keep caches warm across long gaps; cross-burst savings come from compact files (`STATUS.md`, summaries, archives), not from cache.
3. **A cold continued session is still usually cheaper than a fresh one.** On a cache miss the session re-bills its history once, then hits cache again on following turns; a fresh worker re-derives context through tool calls, paying input *and* output *and* wall-clock time. Choose fresh only on the contamination/relevance criteria above.

---

## Report Compression

Full logs, full diffs, full stack traces, and long command output in reports are a cache-hygiene anti-pattern. They bloat the report, which becomes fresh (uncached) input for the coordinator during report intake.

**Rules:**

- **Forbid** pasting full logs, full diffs, full stack traces, or long command output into reports.
- **Require** concise summaries + short excerpts (max ~10 lines) + file paths to full logs or artifacts.
- Report findings should state what changed and why, not reprint the entire output.
- **Budget targets:** task files should stay <=4 KB, ordinary reports <=3 KB, and review reports <=5 KB. Larger evidence belongs under `.agent-inbox/artifacts/<task-id>/` with a path reference in the report.
- **Coordination artifacts rule:** briefs, specs, and scratch notes created by the coordinator must live under `.agent-inbox/` (not the workspace root). Files there are gitignored and excluded from out-of-scope checks; a file at the workspace root will be flagged as an out-of-scope worker change. Put long checklists or field lists in a `.agent-inbox/brief-*.md` file and point to it from the task's `read_first` — it does not count toward the task-file budget.

**Example (bad):**

```
## Commands Run
$ python -B scripts/validate-agent-inbox.py examples/fixtures/valid/
[...200 lines of output...]
```

**Example (good):**

```
## Commands Run
$ python -B scripts/validate-agent-inbox.py examples/fixtures/valid/
exit 0 — all 6 valid fixtures passed. Full output at: artifacts/validate-valid.log
```

---

## Event Log and Status Board Guidance

- `events.jsonl` entries are append-only and compact. Keep them that way. Do not embed report content, diffs, or long summaries in event entries.
- `STATUS.md` is regenerated by `afc-status.py`. Do not hand-edit it to include extra prose. The eight-column table is the intended format.
- Both files are coordinator-read on most turns. Compact content means more of the file stays cached.

---

## Cache-Regression Definition

A **cache regression** is any change that reduces the effective cache-hit ratio for the coordinator or workers without an offsetting improvement. Indicators:

- Coordinator per-turn input tokens increase by >10% on a task shape where no new consumption source was added.
- Worker report size grows significantly without new required evidence.
- A previously-stable prompt section is reordered or expanded, breaking the cache prefix.

When a cache regression is suspected, measure before and after using token accounting methodology and record the delta in the Coordinator-Behavior Change Log.

---

## Recommended Prompt Layouts

### Coordinator prompt structure (per turn)

```
[Skill body — cached after turn 1]
[Roster — cached after first read]
[Task file(s) — cached per task]
[Report file(s) — fresh input, keep compact]
[Evidence files — open only specific changed_files paths]
```

### Worker prompt structure (per turn)

```
[Task file — cached after first read]
[Source files being edited — cached per file]
[Report being written — stable prefix, dynamic findings at the end]
```

---

## Hygiene Reminders

The protocol is runtime-optional, so reminders cannot rely on a daemon. They attach to surfaces that already run (backlog item I3):

| Condition | Reminder | Surface |
|---|---|---|
| Closed/cancelled/superseded files still in the active inbox | `HINT: <N> closed task/report files in active inbox — archive to .agent-inbox/archive/<YYYY-MM>/` | `afc-status.py`, `afc-poll.py` |
| Active set over size threshold (default 100 KB) | `HINT: active inbox is <N> KB — archive or summarize before the next coordinator turn` | `afc-status.py`, `afc-poll.py` |
| Task in `ASSIGNED`/`RUNNING` with no report past a stale threshold | `HINT: task <id> has no report after <N> polls — check the worker or mark it BLOCKED` | `afc-poll.py` |
| Task/report size over budget | `WARN: <N> task/report file(s) exceed budget — move logs to artifacts/<task-id>/` | `afc-status.py`, `afc-poll.py`, `afc-snapshot.py` |
| `SKILL.md` in the tolerance band | `WARN: SKILL SIZE: ... over the 8000 byte target ...` (passes; trim soon) | `audit-docs.py` |
| `SKILL.md` over the hard ceiling | CI fails (`audit-docs.py check_skill_size`, over `SKILL_SIZE_HARD = 9000` bytes) | `audit-docs.py` |

**Named constants (I3):**

- `ACTIVE_INBOX_HINT_LIMIT_BYTES = 100 * 1024` — size threshold for top-level active task/report files only; events, status/spec metadata, archived files, and `artifacts/` evidence are excluded.
- `TASK_BUDGET_BYTES = 4 * 1024`, `REPORT_BUDGET_BYTES = 3 * 1024`, `REVIEW_REPORT_BUDGET_BYTES = 5 * 1024` — advisory size budgets for active coordination files. The routing inline-context gate uses a matching `MAX_FULL_CONTEXT_BYTES = 4 * 1024`.
- `SKILL_SIZE_TARGET = 8000` / `SKILL_SIZE_HARD = 9000` — two-tier byte budget for `SKILL.md` (the only always-loaded file), enforced by `audit-docs.py check_skill_size` in CI. At/below the target the gate is clean; in the `8000 < size <= 9000` tolerance band it passes with an advisory `WARN` (so a small edit no longer forces a byte-shaving commit); above the hard ceiling CI fails. Both values may only ratchet down; raising either requires explicit maintainer acceptance in the PR description.
- `CLOSED_STATUSES = ("CLOSED_GO", "CLOSED_PARTIAL", "CLOSED_RED", "CANCELLED", "SUPERSEDED")` — closed states from `references/archive-policy-v0.1.md`.
- Stale-task hints are advisory and deterministic in the status/poll surfaces that have a date source.

**Rules:** hints are single lines, deterministic, and advisory — scripts never act on them. The coordinator may surface at most one hint line per verdict; anything more belongs in `STATUS.md`. Each script emits at most one hint per fired rule (one-hint-per-verdict).

---

## Active Inbox Hygiene Pointer

The first reminder in this file points to the archive policy. The full
policy (active states, closed states, manual archive path, heavy-artifact
placement, filename preservation, rollback guidance) lives in
`references/archive-policy-v0.1.md` and is intentionally **not** duplicated
here. The single line of policy the coordinator needs to remember is:

- Active states stay in `.agent-inbox/`; closed states move to
  `.agent-inbox/archive/<YYYY-MM>/`; heavy artifacts live under
  `.agent-inbox/artifacts/<task-id>/` and are outside the default
  coordinator context.
Use `scripts/afc-close.py --dry-run --task-id <TASK_ID> --status <CLOSED_STATUS>` for the one-task scripted path; keep batch cleanup manual until a later, explicitly approved change.

Everything else (the exact state list, the manual workflow, the rollback
steps) is on-demand reading from the reference document.

---

## Implementation Checklist

Use this checklist when adding or modifying protocol artifacts:

- [ ] Stable content (frontmatter, scope, guardrails) appears before dynamic content (findings, evidence).
- [ ] Reports contain summaries and paths, not full output.
- [ ] Task files are under ~4 KB; split larger tasks.
- [ ] Event log entries are compact, no embedded diffs or logs.
- [ ] Coordinator does not re-read unchanged files on every turn.
- [ ] Related follow-up tasks go to the worker session that already holds the context, unless that session is contaminated.
- [ ] Dialogue with one worker is batched within the cache window where practical; worker model stays fixed per session.
- [ ] Report frontmatter uses `schema: agent-file-coordination/report` (not filename convention) for programmatic detection.
- [ ] New fixtures verify schema-based detection, not filename-based detection.

---

## References

- `SKILL.md` — protocol definition and handoff format.
- `references/worker-brief.md` — worker report requirements and permission rules.
- `templates/TEMPLATE_REPORT.md` — report template structure.
- `references/archive-policy-v0.1.md` — active-vs-closed split, manual archive path, and heavy-artifact placement. The reminder line above points there for the full policy; do not duplicate the full policy in this file.
