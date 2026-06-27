---
schema: agent-file-coordination/worktree-locks
schema_version: 0.1.0
updated_at: 2026-06-08
---

# Worktree Locks

> Pre-existing worktree locks file used to verify that `afc-init`
> refuses to overwrite existing `.agent-inbox/` content.

| lock_id | task_id | owner_agent | workspace_mode | worktree_path | branch | locked_files_or_areas | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| refuse-fixture-lock | refuse-fixture-task | Refuse-Test | read_only_shared | <WORKTREE_PATH> | main | <FILE_OR_DIR_LIST> | ACTIVE |
