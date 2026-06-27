---
schema: agent-file-coordination/worktree-locks
schema_version: 0.1.0
updated_at: 2026-06-08
---
# Worktree Locks

| lock_id | task_id | owner_agent | workspace_mode | worktree_path | branch | locked_files_or_areas | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lock-real | real-task-001 | Implementer | manual_worktree_needed | <PROJECT_ROOT>-worktrees/fix | task/fix | src/ | ACTIVE |
| lock-orphan | ghost-task-999 | Reviewer | read_only_shared | <PROJECT_ROOT> | main | read-only | ACTIVE |
