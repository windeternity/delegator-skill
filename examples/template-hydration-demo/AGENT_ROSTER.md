---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---

# Agent Roster

| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Coordinator | coordinator | file reader/writer | high-reasoning | Local IDE | full-skill | yes | yes | bounded | yes | no | can_create_or_assign | task decomposition, evidence review, final verdict | routine worker loops | Primary coordinator |
| Reviewer | reviewer | read-only search | high-reasoning | Local IDE | task-only | no | no | none | yes | no | read_only_shared | guardrail review | edits, final approval | Strict read-only worker |
| Implementer | implementer | file reader/writer | code-specialized | Local IDE | worker-brief | no | yes | tests_only | yes | no | manual_worktree_needed | bounded implementation | broad refactor, final approval | Worker with no coordinator authority |
