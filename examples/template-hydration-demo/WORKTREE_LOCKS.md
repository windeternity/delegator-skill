---
schema: agent-file-coordination/worktree-locks
schema_version: 0.1.0
updated_at: 2026-06-08
---

# Worktree Locks

| lock_id | task_id | owner_agent | workspace_mode | worktree_path | branch | locked_files_or_areas | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lock-reviewer-read-only | task-reviewer-guardrail-audit | Reviewer | read_only_shared | <PROJECT_ROOT> | main | read-only | RELEASED |
| lock-implementer-small-fix | task-implementer-small-fix | Implementer | manual_worktree_needed | <PROJECT_ROOT>-worktrees/small-fix | task/small-fix | docs/QUICKSTART.md | ACTIVE |
