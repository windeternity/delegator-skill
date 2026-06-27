---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---

# Agent Roster

> Pre-existing roster file used to verify that `afc-init` refuses to
> overwrite existing `.agent-inbox/` content without an explicit
> `--force` / `-Force` flag.

| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Refuse-Test | reviewer | read-only | high-reasoning | local-ide | task-only | no | no | none | yes | no | read_only_shared | refuse-to-overwrite regression | edits | placeholder for the refuse-to-overwrite fixture |
