---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---
<!-- LOCAL-ONLY: never commit this file. It is the user-level roster source of
truth, read directly by external-dispatch gates. Configure workers once here
and every project reuses them; sync-skill.ps1 preserves LOCAL_* across updates. -->

# Local Agent Roster

<!-- HYDRATION: Replace all <PLACEHOLDER> values with your real worker/model/CLI
aliases. This file lives in the installed Skill directory (e.g.
~/.claude/skills/agent-file-coordination/LOCAL_ROSTER.md) and is shared across
projects. Placeholder-only rosters block external dispatch. Current-session
subagents, built-in helpers, internal multi_agent calls, and chat-only calls
inside the coordinator runtime are not AFC workers. A project may override this
only with an explicit project-override marker in .agent-inbox/AGENT_ROSTER.md. -->

<!-- SESSION PREFERENCES
Default CAL: <CAL-1_OR_CAL-2_OR_CAL-3>
Execution preference: <PREFERRED_AGENT_TOOL_MODEL_PAIRS_AND_AVOID_LIST>
Available resources: <TOOLS_PROVIDERS_ACCOUNTS_LOCAL_RUNTIMES_AND_LIMITS>
Available now: <USABLE_WORKERS_CLIS_PROVIDERS_LOCAL_RUNTIMES>
Model preference order: <PREFERRED_MODELS_AND_FALLBACKS>
Avoid / unavailable: <MODELS_TO_AVOID_PAUSED_ROUTES_OR_KNOWN_LIMITS>
Smoke tests: <LAST_KNOWN_SMALL_TEST_OR_UNKNOWN>
Confirmed: <YYYY-MM-DD>
Change policy: keep these defaults until the user asks to change them or a route becomes unavailable.
-->

| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| <COORDINATOR_NAME> | coordinator | <TOOL_NAME> | <MODEL_NAME> | <PROVIDER_OR_PATH> | full-skill | yes | yes | bounded | yes | yes | <WORKTREE_CAPABILITY> | task decomposition, evidence review, final verdict | routine worker loops | <NOTES> |
| <WORKER_NAME_1> | <ROLE> | <TOOL_NAME> | <MODEL_NAME> | <PROVIDER_OR_PATH> | <PROTOCOL_MODE> | no | <YES_OR_NO> | <COMMAND_LEVEL> | <YES_OR_NO> | <YES_OR_NO> | <WORKTREE_CAPABILITY> | <BEST_USE> | <AVOID> | <NOTES> |
| <WORKER_NAME_2> | <ROLE> | <TOOL_NAME> | <MODEL_NAME> | <PROVIDER_OR_PATH> | <PROTOCOL_MODE> | no | <YES_OR_NO> | <COMMAND_LEVEL> | <YES_OR_NO> | <YES_OR_NO> | <WORKTREE_CAPABILITY> | <BEST_USE> | <AVOID> | <NOTES> |

<!-- CAL-3 workers also need a callable, probe-verified binding. By default that
lives in LOCAL_INVOKE_RECIPES.json next to this file (also preserved by
sync-skill). Never put API keys/tokens here — reference env var names instead.

Suggested values:
  Role: coordinator / planner / implementer / reviewer / smoke / docs / research / other
  Protocol Mode: full-skill / worker-brief / task-only / manual-paste / unknown
  Coordinator Authority: yes / no / limited
  Command Level: none / read_only / tests_only / bounded
  Worktree Capability: can_create / can_use_existing / read_only_shared / manual_needed / unknown

  Minimum for dispatch:
  - Default CAL must be a concrete CAL-1, CAL-2, or CAL-3.
  - At least one non-coordinator external worker row must be fully hydrated.
  - CAL-1/CAL-2 workers may be user-relayed external chats/tools/sessions.
  - CAL-3 workers need callable invoke recipes and successful probe evidence.
  - LOCAL_INVOKE_RECIPES.json is NOT a substitute for this roster.
  - Completion still requires the expected report/evidence path; chat "done"
    alone is not accepted.
-->
