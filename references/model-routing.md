# Model / Tool Routing Reference

Use this as the stable routing layer for coordinating several external agents. It is not a benchmark truth table and it intentionally avoids hard-coding vendor or personal agent names.

For generic model/tool capability mapping, read:

```text
references/current-model-tool-routing-2026.md
references/vibe-coding-model-task-matrix.md
```

For a concrete model label that is not already known in the current project roster, use:

```text
references/unknown-model-discovery.md
references/model-profile-template.md
```

Do not keep durable claims about fast-changing concrete model names in this stable routing file.

`references/vibe-coding-model-task-matrix.md` is a practical allocation
checklist for matching known model labels to task shapes. Treat it as a
suggestion layer only: first apply capability, safety, tool-access, and roster
gates; then use the matrix to choose between otherwise suitable model/tool
pairs. If a user's model is not listed in the matrix, follow
`references/unknown-model-discovery.md` and classify it by observed capabilities
instead of forcing it into a known label.

## General Rules

- Route by task shape first, model/tool second.
- **Capability-first routing:** task requirements (file access, command execution, worktree creation, visual input, report writing) are the primary routing criteria. An agent that lacks a required capability must not be assigned, regardless of user preference.
- **Safety-first routing:** if a task involves destructive risk, production changes, or security-sensitive areas, route to the agent with the strongest review or guardrail capability, even if another agent is preferred for speed or cost.
- **Tool-access routing:** if a task requires a specific tool (e.g., browser, worktree creation, local runtime), route to the agent that has that tool. Do not assign tool-dependent tasks to agents that lack the tool.
- **User preference is secondary:** user preference order (e.g., "use Agent X first") applies only when it does not materially conflict with capability, safety, or tool-access requirements. If a preferred agent lacks a required capability or is unsuitable for the risk profile, state the reason and route to a better-fit agent.
- Keep `Agent Name` separate from `Model / Tool / Capability Hint`.
- Do not invent model names, vendor names, or agent names.
- Prefer fast, narrow agents for small fixes.
- Use strong reviewers for guardrails, merge readiness, destructive-risk decisions, and production go/no-go.
- Use long-context models only when the task truly needs long context or many steps.
- If a model/tool has just shown slow or weak performance in this project, down-rank it for urgent tasks.
- Do not let the same agent both implement and be the final reviewer for high-risk changes.
- Put current-user observations above generic marketing claims.
- When external workers are available, default execution to them. The coordinator should not fall through to local implementation for routine work when a suitable external agent can handle it.
- Use concrete model allocation tables only after confirming the user's actual tool access and preferences; do not let a dated table override local smoke-test results.

## First-Use Roster Gate

When no reliable `AGENT_ROSTER.md` exists, do not assign external work yet. First ask the user for the current available agents, tools, models, and capabilities, or create the roster directly if the current conversation already provides enough detail.

Capture:

```markdown
| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

Required decisions before routing:

- canonical `Agent Name`, separate from model identity
- actual tool/model if known
- role and protocol mode
- edit/command/browser/worktree capability
- final coordinator authority

Ask only for what is needed. If the user's message already provides enough information, create or update the roster directly.

## Generic Role Matrix

| Agent Capability Type | Best Use | Avoid | Notes |
| --- | --- | --- | --- |
| Coordinator / final judge | route selection, task decomposition, synthesis, merge/go-no-go, destructive-risk judgment | routine long test execution | Should make final `GO / PARTIAL / RED` from evidence. |
| Fast implementation agent | small/mid code edits, docs fixes, targeted tests, structured outputs | final high-risk review, broad ambiguous architecture calls | Good default for bounded implementation when repo access is available. |
| Strong review agent | PR/diff review, guardrail audit, logic bug tracing, branch equivalence, release risk check | making production edits without separate review | Best as an independent reviewer. |
| Long-horizon execution agent | multi-step repo traversal, long test-fix loops, large refactors with clear acceptance criteria | final release approval, destructive cleanup | Needs tight scope and report requirements. |
| Long-context synthesis agent | large docs, cross-thread handoff, roadmap consolidation, multi-agent planning | tiny hotfixes or urgent low-latency work | Useful when organizing context is the task. |
| Visual / multimodal agent | screenshots, UI layout, PDF/image/video plus code, browser visual diagnosis | final code safety audit | Pair with a reviewer when code changes are proposed. |
| Runtime smoke agent | local service launch, API/browser smoke, environment reproduction | broad product judgment | Should report exact commands, URLs, logs, and observed results. |

## Default Routing Patterns

| Task Shape | Preferred Routing |
| --- | --- |
| Data/source connectivity reproduction | Runtime smoke or fast implementation agent with local environment access. |
| Guardrail diff audit | Strong review agent, read-only by default. |
| Frontend screenshot/UI issue | Visual/multimodal agent if visual evidence matters; otherwise fast implementation agent. |
| Browser/API smoke | Runtime smoke agent using the same integration worktree that will be launched. |
| Long implementation chain | Long-horizon execution agent with a strong reviewer after implementation. |
| Multi-agent task board / handoff docs | Coordinator or long-context synthesis agent. |
| Final merge/go-no-go/high-risk cleanup | Coordinator/final judge, optionally after independent strong review. |
| Simple docs/string cleanup | Any fast implementation agent; avoid expensive long-context routing. |

## Worktree Capability Notes

Model choice and workspace mode are separate decisions.

- Agents that run inside coding environments may be able to create worktrees if instructed, but still give exact path, branch, and base.
- IDE agents without worktree tooling may need the coordinator/user to create a worktree first, or the user may need to tell the agent to open the provided Git repo/worktree.
- Slow or less reliable agents should not be asked to create and manage many worktrees; give them one exact existing path.
- Reviewers generally do not need a new worktree unless they are auditing a specific branch in isolation.
- Runtime smoke agents should use the integration worktree that will actually be launched.

## Capability Calibration

Do not assume that a model/tool is the default executor just because it is new, popular, or marketed as agentic.

Record observations in the roster or handoff when useful:

```markdown
| Agent Name | Observed Strength | Observed Weakness | Routing Adjustment |
| --- | --- | --- | --- |
| Implementer | fast targeted edits | weak final review | use for implementation, pair with Reviewer |
| Reviewer | catches guardrail drift | slow at repo-wide traversal | use after diff is ready |
```

## Task File Addition

When model/tool choice matters, add this section:

```markdown
## Model / Tool / Capability Hint
- preferred: <agent, model, tool, or capability type>
- reason: <why this fit matches the task shape>
- fallback: <optional fallback>
- reviewer: <optional independent reviewer>
- verification: official / reported / provider_label / local_label / unknown
- smoke_test_needed: yes / no
```

## Override Rules

Override the routing table when:

- the user explicitly assigned an agent
- the agent roster or handoff gives a canonical name
- the model/tool is queued, too slow, unavailable, or lacks repository access
- the task requires a tool only one agent has
- recent performance in this project contradicts the table
- worktree/file ownership would cause conflicts

## Routing Priority

When multiple routing criteria conflict, apply them in this order:

1. **Capability gate:** the agent must have the required capabilities (edit, commands, worktree, visual, report writing). If it lacks a required capability, it is disqualified.
2. **Safety gate:** for destructive-risk, production, or security-sensitive tasks, prefer the agent with the strongest review or guardrail capability.
3. **Tool-access gate:** if the task requires a specific tool, route to the agent that has it.
4. **Task-shape match:** prefer the agent whose strengths match the task shape (fast fix, long implementation, review, smoke test, etc.).
5. **User preference:** when all above criteria are satisfied, apply user preference order.
6. **Cost/latency:** when multiple agents are equally fit, prefer the cheaper or faster option.

User preference does not override capability, safety, or tool-access gates. If the preferred agent is disqualified, state the reason and route to the next best-fit agent.
