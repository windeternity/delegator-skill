---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---

# Agent Roster

| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lead | coordinator | file reader/writer | high-reasoning | Local IDE | full-skill | yes | yes | bounded | no | branch, share | Task decomposition and final verdict | Heavy coding | Codex-first coordinator |
| Worker | implementer | file reader/writer | code-specialized | Local IDE | task-only | no | yes | tests_only | no | existing_edit_worktree | Small bounded edits | Refactoring | Worker with no coordinator authority |
