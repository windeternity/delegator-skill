---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---

# Agent Roster

<!-- HYDRATION: Replace all <PLACEHOLDER> values with your project-local data.
User-specific worker/model/CLI aliases belong here, not in public defaults. -->

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

<!-- Suggested values:
  Role: coordinator / planner / implementer / reviewer / smoke / docs / research / other
  Protocol Mode: full-skill / worker-brief / task-only / manual-paste / unknown
  Coordinator Authority: yes / no / limited
  Command Level: none / read_only / tests_only / bounded
  Worktree Capability: can_create / can_use_existing / read_only_shared / manual_needed / unknown
-->
