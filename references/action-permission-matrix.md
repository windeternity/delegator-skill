# Action Permission Matrix

Use this matrix to decide what an assigned agent may do. Project-specific instructions can be stricter, but should not be weaker unless the user explicitly approves the risk.

Before assigning external agents, the coordinator must establish a project-local roster or confirm equivalent current model/tool/capability details in the conversation. Do not use private installed profile contents in reusable source docs, examples, fixtures, or reports.

| Action | Default | Requires Explicit User Approval | Notes |
| --- | --- | --- | --- |
| Read tracked project files | allowed | no | Stay within the assigned repo/worktree. |
| Write the assigned report file | allowed only when `write_reports: yes` | no | Must use the specified `Report Path` and include evidence refs and guardrail confirmation. |
| Create or modify `.agent-inbox/` task files | blocked unless `write_task_files: yes` | yes, via coordinator assignment | Ordinary workers should normally have `write_task_files: no`. |
| Create or modify coordination status/lock files | coordinator-only by default | yes, via task assignment | Use for status boards, worktree locks, or handoffs; do not include secrets or private raw data. |
| Modify docs/examples in assigned scope | allowed only if task says edit-capable | yes, via task assignment | Keep edits bounded. |
| Modify source code | blocked unless task says edit-capable | yes | Must include validation tier and changed-file report. |
| Run read-only commands | allowed when needed | no | Examples: `git status`, `git diff`, `ls`, targeted test discovery. |
| Run tests/builds | allowed if task includes validation | no, unless expensive/destructive | Report exact commands and result. |
| Install dependencies | blocked by default | yes | Can change environment state. |
| Start local services | blocked unless task asks for smoke/runtime check | yes, via task assignment | Report ports/URLs; do not expose publicly. |
| Read `.env`, secrets, tokens, private credentials | blocked | no normal approval | Prefer asking user to confirm presence without printing values. |
| Print or copy secrets/private data into reports | blocked | never | Redact instead. |
| Commit | blocked | yes | Include exact commit scope and message if authorized. For Release-Operator: `commit_push: approved` in task frontmatter. |
| Push | blocked | yes | Never push by implication. For Release-Operator: report-before-commit required. |
| Open PR | blocked | yes | Requires clean diff summary. For Release-Operator: staged-file allowlist check required. |
| Merge PR | blocked | yes | Requires coordinator final GO. Release-Operators may NOT merge. |
| Respond to PR review (fix-only) | blocked | yes | Review-Responder variant of Release-Operator. Scoped to one PR; fix-only; report each comment addressed. |
| Delete branch/worktree | blocked | yes | Destructive cleanup; require final confirmation. |
| Force push / reset hard / clean untracked | blocked | yes, high-risk | Avoid delegating. |
| Deploy / production switch | blocked | yes, high-risk | Requires explicit deployment task. |
| Change permissions, billing, cloud resources | blocked | yes, high-risk | Do not delegate without a dedicated approval trail. |

## Task File Requirement

Every task file should state:

```markdown
## Permission Scope
- read_files: yes / no
- write_reports: yes / no
- write_task_files: yes / no
- modify_source: yes / no
- run_commands: none / read_only / tests_only / bounded
- network_access: none / docs_only / allowed
- commit_push: no / ask / approved
- destructive_actions: no
```

`write_reports` authorizes writing only the assigned report file. `write_task_files` authorizes creating or modifying task files and should be reserved for coordinators or explicitly limited sub-coordinators.

### Branch-command permission rule

When a task requires a worker to create or switch branches, use `run_commands: bounded` — not `tests_only`. The `tests_only` level permits running tests and read-only inspection commands only; it does not cover `git switch`, `git checkout -b`, or other branch-creating operations.

| Task intent | Correct `run_commands` | Example commands |
| --- | --- | --- |
| Read-only inspection | `read_only` | `git status`, `git diff`, `git log` |
| Run tests / builds only | `tests_only` | `python -m pytest`, `npm test` |
| Narrow non-destructive git operations (branch create/switch) | `bounded` | `git switch -c <branch>`, `git checkout -b <branch>` |

Keep `commit`, `push`, `merge`, `rebase`, `reset`, `clean`, and destructive operations default-deny. Only a release-operator task with explicit `commit_push: approved` may perform those.

Never combine `run_commands: tests_only` with a task body that requires `git switch`, `git checkout -b`, or branch setup — this is a contradiction that blocks the worker.

## Worker Role Fields

Every worker task should also state:

```markdown
## Role Boundary
You are the assigned worker agent for this task, not the coordinator.
Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
If more work is needed, write it in the report as a recommendation.
```

The task metadata should include `role`, `protocol_mode`, and `coordinator_authority`. Ordinary workers default to `protocol_mode: task-only` or `protocol_mode: worker-brief` and `coordinator_authority: no`.

## Default Deny Rule

If an action is not mentioned in the task file and is not obviously required for the task, treat it as blocked and ask the coordinator/user before proceeding.
