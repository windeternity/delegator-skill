# Current Model / Agent Tool Routing Reference 2026

> **Example only.** This is a dated, illustrative reference — NOT a maintained benchmark or endorsement. Concrete model names, capabilities, pricing, and tool compatibility change frequently and may be outdated. Use it as a pattern for how to think about routing, and maintain real model facts in your own project-local roster.

Last reviewed: 2026-06-05

Use this as a dated, practical routing reference. It is not a benchmark leaderboard. Model quality, price, access, and tool compatibility change quickly, so always let the user's real available tools and recent observations override this table.

## First Principle

Route by four layers, in this order:

1. Task shape: implementation, review, smoke, UI, research, handoff, merge judgment.
2. Agent tool: Codex, Claude Code, OpenCode, Gemini CLI, Cursor, Copilot, Cline/Roo/Kilo, local IDE agent, or other.
3. Model fit: reasoning, coding, long context, multimodal, cost, latency, language, local/private deployment.
4. Integration quality: native > official third-party provider > OpenAI-compatible gateway > unofficial bridge.

Do not assign work only because a model is popular.

## Generic Model Capability Taxonomy

Use this capability taxonomy before choosing a specific model brand. A model family may be strong in more than one category, but the coordinator should pick the capability that proves the task.

| Capability | What It Means | Best Tasks | Watch For |
| --- | --- | --- | --- |
| Reasoning / planning | Multi-step decomposition, trade-off analysis, route selection, contradiction detection | project planning, architecture review, final GO/RED, blocker diagnosis | can over-plan; require concrete acceptance criteria |
| Coding implementation | Produces correct code edits across one or more files | bug fixes, feature slices, refactors, tests | must be paired with tests and diff review |
| Code review / audit | Reads diffs critically and finds regressions, scope drift, security or data issues | PR review, guardrail audit, merge readiness, release checks | do not use the same agent as implementer and final reviewer for risky changes |
| Tool calling / agentic execution | Reliably uses shell, file edits, browser, MCP, APIs, or external tools | long execution loops, environment reproduction, local smoke, task automation | integration quality matters more than raw model score |
| Long context | Handles large repos, long docs, prior handoffs, logs, or multi-file evidence | handoff synthesis, repo-wide reading, large document packs, long bug trails | retrieval can still miss details; require file refs/evidence |
| Multimodal / visual | Understands screenshots, UI states, diagrams, PDFs, video frames, or visual bugs | frontend diagnosis, layout review, design QA, visual evidence | pair with code reviewer if implementation changes follow |
| Search / external knowledge | Uses web or search-grounded evidence well | market research, docs lookup, dependency changes, current model/tool checks | cite sources; do not treat dated claims as permanent |
| Structured output | Produces reliable JSON, tables, reports, checklists, and machine-readable summaries | task files, report files, status boards, payload checks | validate schema when downstream tools consume it |
| Language / localization | Strong in the user's working language and domain phrasing | Chinese engineering notes, bilingual docs, user-facing copy | avoid awkward literal translation for product text |
| Low-latency execution | Fast enough for small loops and frequent iterations | tiny fixes, command retries, formatting, test reruns | may be weaker for deep reasoning; keep scope narrow |
| Cost efficiency | Good enough quality at lower cost | routine implementation, second opinions, bulk review drafts | do not let cheap models be sole approver for high-risk changes |
| Local / private deployment | Runs in local or controlled environment | private drafts, sensitive repo reading, offline work | usually needs stronger final review before merge |

## Capability-to-Task Defaults

| Task Type | Primary Capability | Secondary Capability | Typical Agent Tool Fit |
| --- | --- | --- | --- |
| Small bug fix | coding implementation | low-latency execution | native vendor coding agent or general multi-provider agent with proven edit capability |
| Broad refactor | long context | coding implementation | long-context-capable CLI/IDE agent |
| PR/diff review | code review / audit | reasoning / planning | strong review agent; do not use the same agent as implementer for risky changes |
| Final merge judgment | reasoning / planning | code review / audit | coordinator/final judge plus independent reviewer |
| UI screenshot issue | multimodal / visual | coding implementation | visual/multimodal-capable CLI/IDE agent |
| Browser/API smoke | tool calling / agentic execution | structured output | runtime-capable CLI/IDE agent |
| Handoff / roadmap | long context | structured output | long-context synthesis model |
| Market/tool research | search / external knowledge | reasoning / planning | web-capable model/tool; dated reference required |
| Private draft | local / private deployment | structured output | local model runner (LM Studio, Ollama, llama.cpp, etc.) |

## First-Use Inventory Questions

When this skill is used in a project for the first time and no reliable `AGENT_ROSTER.md` exists, ask the user for a compact inventory before routing tasks:

```text
Before I assign agent tasks, tell me what you currently have available:
1. Agent tools: Codex / Claude Code / OpenCode / Gemini CLI / Cursor / Copilot / Cline / Roo / Kilo / other.
2. Models: OpenAI / Claude / Gemini / DeepSeek / Qwen / GLM / Kimi / MiniMax / Grok / Mistral / local models / other.
3. Which tools can edit files, run commands, use browser, create worktrees, or only review read-only?
4. Which model/tool pair do you prefer or want to avoid?
```

If the user already provided enough information, create or update `.agent-inbox/AGENT_ROSTER.md` directly.

## Agent Tool Categories

| Tool Category | Examples | Best Model Pairing | Routing Notes |
| --- | --- | --- | --- |
| Native vendor coding agent | Codex, Claude Code, Gemini CLI, MiniMax Agent/Code, Z Code | Usually best with the vendor's own frontier model | Most stable for tool calling, editing, auth, and permission flows. |
| General multi-provider coding agent | OpenCode, Cline, Roo Code, Kilo Code | Any supported provider; OpenAI-compatible APIs often work | Best when the user wants model freedom. Must verify tool-calling and edit reliability per model. |
| IDE-first agent | Cursor, GitHub Copilot, VS Code agent extensions | Platform-supported model list | Good developer UX. Often strong for inline edits and issue-to-PR flows, but model choice may be gated by product policy. |
| Bridge / switch layer | CC Switch or similar adapters | Can route many OpenAI-compatible or transformed APIs into another tool | Useful but should be marked as bridge-mode. Require smoke test before serious work. |
| Local model runner | LM Studio, Ollama, llama.cpp, vLLM, SGLang | Qwen-Coder, DeepSeek, GLM, Gemma, Mistral, local fine-tunes | Good for privacy and cheap drafts. Do not use as sole final reviewer unless proven in the repo. |

## Tool-Specific Routing

> **Warning:** This section names concrete tools and models for practical orientation, but these are **dated observations**, not durable facts. Always verify current capabilities through the user's project-local roster and a small smoke test before assigning serious work.

### Native vendor coding agents

- **Examples:** Codex, Claude Code, Gemini CLI, MiniMax Agent/Code, Z Code.
- **Best tasks:** coordinator, merge captain, final GO/RED, complex cross-file implementation, code review, security review, repo-scale reasoning.
- **Caution:** Treat as high-trust only when running through official first-party surfaces. Third-party packages that imitate these tools require provenance verification.

### General multi-provider coding agents

- **Examples:** OpenCode, Cline, Roo Code, Kilo Code.
- **Best tasks:** when the user wants freedom to use many providers, custom base URLs, local models, OpenRouter, Vercel AI Gateway, LM Studio, Ollama, llama.cpp, or OpenAI-compatible APIs.
- **Caution:** Do not assume every model handles tool calling, patches, long context, and streaming identically. Require a smoke test before risky work.

### IDE-first agents

- **Examples:** Cursor, GitHub Copilot, VS Code agent extensions.
- **Best tasks:** IDE-first development, inline edits, frontend/backend implementation, developer workflow polish, GitHub issue-to-PR, code completion.
- **Caution:** Model choice may be gated by product policy or plan. Record the chosen model in the roster if exact identity matters for auditability.

### Bridge / switch layers

- **Examples:** CC Switch or similar adapters.
- **Best tasks:** routing many OpenAI-compatible or transformed APIs into another tool.
- **Caution:** Mark as bridge-mode. Require a smoke test before serious work.

### Local model runners

- **Examples:** LM Studio, Ollama, llama.cpp, vLLM, SGLang.
- **Best tasks:** privacy, offline work, low-cost drafts, local/private repo assistance.
- **Caution:** Do not use as sole final reviewer unless proven in the repo. Cap context and verify outputs.

## Model Family Routing

> **Warning:** This table provides **dated orientation** for common model families. It is not a benchmark or permanent truth table. Concrete model versions, capabilities, and access paths change quickly. For any model not already in your project-local roster, follow `references/unknown-model-discovery.md`.

| Capability Dimension | What to Look For | Best Tasks | Watch For |
| --- | --- | --- | --- |
| Reasoning / planning | Multi-step decomposition, trade-off analysis, route selection, contradiction detection | project planning, architecture review, final GO/RED, blocker diagnosis | can over-plan; require concrete acceptance criteria |
| Coding implementation | Produces correct code edits across one or more files | bug fixes, feature slices, refactors, tests | must be paired with tests and diff review |
| Code review / audit | Reads diffs critically and finds regressions, scope drift, security or data issues | PR review, guardrail audit, merge readiness, release checks | do not use the same agent as implementer and final reviewer for risky changes |
| Tool calling / agentic execution | Reliably uses shell, file edits, browser, MCP, APIs, or external tools | long execution loops, environment reproduction, local smoke, task automation | integration quality matters more than raw model score |
| Long context | Handles large repos, long docs, prior handoffs, logs, or multi-file evidence | handoff synthesis, repo-wide reading, large document packs, long bug trails | retrieval can still miss details; require file refs/evidence |
| Multimodal / visual | Understands screenshots, UI states, diagrams, PDFs, video frames, or visual bugs | frontend diagnosis, layout review, design QA, visual evidence | pair with code reviewer if implementation changes follow |
| Search / external knowledge | Uses web or search-grounded evidence well | market research, docs lookup, dependency changes, current model/tool checks | cite sources; do not treat dated claims as permanent |
| Structured output | Produces reliable JSON, tables, reports, checklists, and machine-readable summaries | task files, report files, status boards, payload checks | validate schema when downstream tools consume it |
| Language / localization | Strong in the user's working language and domain phrasing | Chinese engineering notes, bilingual docs, user-facing copy | avoid awkward literal translation for product text |
| Low-latency execution | Fast enough for small loops and frequent iterations | tiny fixes, command retries, formatting, test reruns | may be weaker for deep reasoning; keep scope narrow |
| Cost efficiency | Good enough quality at lower cost | routine implementation, second opinions, bulk review drafts | do not let cheap models be sole approver for high-risk changes |
| Local / private deployment | Runs in local or controlled environment | private drafts, sensitive repo reading, offline work | usually needs stronger final review before merge |

### Dated model family notes (expires 2026-12-31; refresh required)

The following notes are based on public information available on 2026-06-05. They are provided as a starting point for projects without an existing roster. **Do not treat them as durable claims.**

| Model Family | Dated Orientation | Typical Tool Pairing | Notes |
| --- | --- | --- | --- |
| OpenAI GPT / Codex | coding agent workflows, repo reasoning, final synthesis | native vendor coding agent, official API | cost can be high; avoid routine long test loops if a cheaper runner exists |
| Claude (Opus / Sonnet / Haiku) | long-horizon coding, multi-file edits, strong reasoning | native vendor coding agent | third-party bridge instability; match model size to task difficulty |
| Gemini / Gemma | multimodal, long context, search-grounded work | native vendor coding agent, local runners for Gemma | final code safety review should be paired with another reviewer for high-risk changes |
| DeepSeek | reasoning, coding review, cost-effective analysis | general multi-provider agent, local runners | verify provider stability; use independent final review for high-risk actions |
| Qwen / Qwen-Coder | open coding models, broad language support | general multi-provider agent, local runners | function-call/tokenizer details can be model-specific; validate tool parser compatibility |
| GLM / Z.ai | Chinese engineering, hybrid reasoning, agentic/coding focus | native vendor coding agent, general multi-provider agent | final release review should be independent; confirm exact model/version because lines move quickly |
| Kimi / Moonshot | long context, document synthesis, planning | native or API if available | avoid tiny urgent fixes if latency is high; check licensing/provider disclosure for derived models |
| MiniMax M-series | long context, agentic workflows, tool use | native vendor coding agent | native stack preferred; commercial/license terms vary by model/version |
| Grok / xAI | real-time or social/news context, broad conversational reasoning | native or API if available | not first choice for final code merge or repo safety unless proven in the user's toolchain |
| Mistral / Codestral | open/developer-friendly coding, European ecosystem | general multi-provider agent, local runners | may lag frontier models on complex repo-wide tasks; pair with reviewer |
| Local small/medium models | privacy, offline work, low cost, quick drafts | local model runner | not enough for high-risk merge unless project-proven; cap context and verify outputs |

## Practical Assignment Recipes

### Routine bounded implementation

- Primary: fast implementation-capable agent.
- Model: choose from the user's roster based on proven edit capability and cost.
- Reviewer: strong review agent if behavior changes.

### High-risk final review

- Primary: coordinator/final judge.
- Reviewer: independent strong review agent.
- Do not let the same agent implement and approve.

### UI / screenshot / browser evidence

- Primary: visual/multimodal-capable agent from the user's roster.
- Reviewer: code reviewer if implementation changes are made.

### Long documentation and handoff synthesis

- Primary: long-context synthesis agent from the user's roster.
- Validation: compare against project files, do not trust memory alone.

### Local/private draft workflow

- Primary: local model runner from the user's roster.
- Reviewer: cloud frontier model or known strong local model before merge.

## Roster Fields To Capture

When creating `.agent-inbox/AGENT_ROSTER.md`, capture:

```markdown
| Agent Name | Tool | Model | Provider / Access Path | Can Edit | Can Run Commands | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
```

Suggested capability values:

- `native`: model is used through its own first-party coding tool.
- `official_provider`: tool officially supports this provider.
- `openai_compatible`: routed through OpenAI-compatible API or gateway.
- `bridge`: routed through an adapter/switch layer.
- `local`: running through a local runtime.
- `unknown`: do not assign risky work until tested.

## Smoke Test Before Serious Work

For any new model/tool pair, run a small check before assigning real code work:

1. Read one file.
2. Propose a tiny non-destructive edit or review comment.
3. Report exact files touched.
4. Confirm whether commands can run.
5. Confirm whether output format is stable.
6. Confirm whether the agent can write a report file.

Only after this should the coordinator use that pair for implementation, release review, or production-like validation.

## Research Notes

This file is based on public information available on 2026-06-05, including official docs and model repositories for OpenCode, Claude Code, Codex, Gemini CLI, Qwen3-Coder, GLM-4.5, DeepSeek-V3, MiniMax-M1, plus recent reporting around coding agents and model/tool ecosystems. Treat it as a dated routing reference, not a permanent truth table.

## Refresh Policy

- **Expires:** 2026-12-31
- **Refresh required before:** assigning work based on this file after the expiry date.
- **How to refresh:** Follow `references/unknown-model-discovery.md` for any new model/tool pair, update the project-local `AGENT_ROSTER.md`, and run a small smoke test before serious work.
- **Do not commit updated concrete model claims to this repository.** Keep them in project-local roster files instead.
