# Unknown Model Discovery Protocol

Use this when the user names a model, agent, provider, gateway label, or local model that is not already listed in the routing references.

The goal is to avoid two failure modes:

1. Rejecting a usable model just because it is not in the reference table.
2. Guessing a model's ability from its name or hype and assigning it risky work too early.

## Required Behavior

If a model/tool is unknown:

1. Preserve the user's exact label.
2. Do not rename it into a similar known model.
3. Research it using current reliable sources when available.
4. Classify the evidence level.
5. Map it to generic capabilities.
6. Add it to the project roster as provisional.
7. Run a smoke test before serious work.
8. Restrict it to read-only or low-risk tasks until validated.

If web access is available and model capability affects routing, search current
sources instead of relying on memory. Prefer official vendor pages, model cards,
API docs, release notes, or the user's visible tool/provider model list. Record
the source type and date in the roster or task note. If no reliable source is
available, mark the evidence level as `unknown` and route conservatively.

## Evidence Priority

Prefer sources in this order:

1. Official vendor docs, model cards, API docs, release notes.
2. Official GitHub repositories or package docs.
3. Reputable technical reporting or benchmark reports.
4. Provider/gateway model list.
5. User's local tool UI or config.
6. Community posts only as weak supporting evidence.

Use `references/vibe-coding-model-task-matrix.md` as a classification aid after
source review. Match the unknown model to capability buckets such as
implementation, audit, long-context synthesis, multimodal UI, search-grounded
research, low-latency execution, or final judgment. Do not promote the model to
high-risk routing solely because its name resembles a listed model.

## Evidence Levels

| Level | Use When | Routing Consequence |
| --- | --- | --- |
| `official` | Confirmed by vendor or official repo/docs | Can be routed normally if user has access. |
| `reported` | Credible reporting exists but not fully verified in user's environment | Use with caution and smoke test. |
| `provider_label` | Visible in provider/gateway/agent UI but official identity is unclear | Treat as real access path, not official model fact. Smoke test required. |
| `local_label` | Local runtime name, quantization, or custom alias | Record runtime limits. Use cautiously. |
| `unknown` | Cannot verify identity/capability | Read-only or low-risk only until user provides docs or smoke test passes. |

## Capability Mapping Template

When adding an unknown model to `.agent-inbox/AGENT_ROSTER.md`, fill this compact profile:

```markdown
### Model Discovery - <exact user label>

- exact_label: <as user wrote it>
- evidence_level: official / reported / provider_label / local_label / unknown
- source_summary: <one-line summary of what was found>
- access_path: native / official_provider / openai_compatible / bridge / local / unknown
- likely_capabilities:
  - reasoning_planning: high / medium / low / unknown
  - coding_implementation: high / medium / low / unknown
  - code_review_audit: high / medium / low / unknown
  - tool_calling_agentic: high / medium / low / unknown
  - long_context: high / medium / low / unknown
  - multimodal_visual: high / medium / low / unknown
  - search_external_knowledge: high / medium / low / unknown
  - structured_output: high / medium / low / unknown
  - language_localization: high / medium / low / unknown
  - latency_cost: fast / balanced / expensive / unknown
  - local_private: yes / no / unknown
- best_use: <task shapes>
- avoid: <risk boundaries>
- smoke_test_needed: yes
```

## Smoke Test

Before serious code work, assign a tiny validation task:

```markdown
# Task - <Agent Name> model-tool smoke

## Purpose
Validate whether this model/tool pair can safely participate in this project.

## Scope
Read-only unless explicitly approved.

## Required Checks
1. Read one project file.
2. Produce a structured summary with file path references.
3. If edit-capable, propose one tiny non-destructive edit but do not apply it unless asked.
4. Confirm whether shell commands are available.
5. Confirm whether browser/visual input is available.
6. Confirm whether worktree creation is supported.
7. Write the report to the specified report path.

## Verdict
GO / PARTIAL / RED
```

## Routing After Smoke

| Smoke Result | Allowed Routing |
| --- | --- |
| `GO` | May receive tasks that match observed capability, still with normal guardrails. |
| `PARTIAL` | Use only for narrow tasks matching observed strengths. Pair with reviewer. |
| `RED` | Do not use for project work until configuration/model access is fixed. |
| No smoke possible | Read-only, low-risk, or user-supplied research only. |

## High-Risk Rule

Even if an unknown model passes smoke, do not use it as the sole authority for:

- final merge approval
- destructive cleanup
- deployment
- security/privacy judgment
- production replay
- financial/legal/medical high-stakes decisions

Require an independent reviewer or coordinator final judgment.

## Do Not Persist Globally Too Early

Do not add an unknown model to the reusable reference tables just because one user has it. First keep it in the project roster. Promote it to a reusable reference only if it becomes broadly useful across projects and the identity/capability is reasonably verified.
