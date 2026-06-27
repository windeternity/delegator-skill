---
schema: agent-file-coordination/worktree-locks
schema_version: 0.1.0
updated_at: <YYYY-MM-DD>
---

# Worktree Locks

<!-- HYDRATION: Replace all <PLACEHOLDER> values with your project-local data. -->

| lock_id | task_id | owner_agent | workspace_mode | worktree_path | branch | locked_files_or_areas | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <LOCK_ID> | <TASK_ID> | <AGENT_NAME> | <WORKSPACE_MODE> | <WORKTREE_PATH> | <BRANCH_NAME> | <FILE_OR_DIR_LIST> | <LOCK_STATUS> |

<!-- Workspace mode values: read_only_shared / existing_edit_worktree / dedicated_worktree_required / manual_worktree_needed
  Lock status values: ACTIVE / RELEASED / BLOCKED / STALE / SUPERSEDED -->
