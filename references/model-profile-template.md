# Model Profile Template

Use this template when a user names a concrete model, provider label, gateway alias, or local model that is not already known in the current project roster.

Do not treat this repository as a live benchmark source. Concrete model names and capabilities must be discovered at project time from current sources or from the user's actual toolchain.

## Discovery Record

```markdown
# Model Discovery - <exact user label>

## Identity
- exact_user_label: <copy exactly>
- vendor_or_provider: <vendor/provider/unknown>
- access_path: native / official_provider / openai_compatible / bridge / local / unknown
- tool_surface: Codex / Claude Code / OpenCode / Gemini CLI / Cursor / Copilot / Cline / Roo / Kilo / local runner / other
- evidence_level: official / reported / provider_label / local_label / unknown
- last_verified: <YYYY-MM-DD>
- sources_checked:
  - <official docs / model card / API docs / release notes / provider list / local config>

## Capability Map
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

## Routing
- best_use: <task shapes>
- avoid: <risk boundaries>
- smoke_test_needed: yes / no
- independent_review_required_for_high_risk: yes

## Smoke Result
- verdict: GO / PARTIAL / RED / not_run
- observed_strengths: <short notes>
- observed_failures: <short notes>
- allowed_task_scope: <what this model/tool pair may do now>
```

## Promotion Rule

Keep concrete model profiles inside the project-local `.agent-inbox/AGENT_ROSTER.md` first. Only promote a model into reusable documentation if it is broadly useful, verified by current sources, and not likely to mislead future users.
