# Worktree Layout Guidance

Use this reference when assigning editing work to multiple agents.

## Recommended Layout

Keep the primary repository and its worktrees as siblings under the same parent directory.

```text
<projects-root>/
├─ <repo-name>/                  # primary checkout / stable baseline
└─ <repo-name>-worktrees/         # container for temporary task worktrees
   ├─ <task-or-pr-a>/
   ├─ <task-or-pr-b>/
   └─ <review-or-smoke-c>/
```

Example:

```text
C:\Projects\my-repo
C:\Projects\my-repo-worktrees\feature-auth-refactor
C:\Projects\my-repo-worktrees\review-auth-refactor
```

## Coordination Directory Layout

When coordination inbox files must live outside the source repository (e.g., cross-agent reports, coordinator verdicts that should not be committed), use a separate sibling directory with a clearly distinct name:

```text
<projects-root>/
├─ <repo-name>/                       # primary checkout / stable baseline
├─ <repo-name>-worktrees/              # actual git worktrees
│   ├─ <task-or-pr-a>/
│   └─ <task-or-pr-b>/
└─ <repo-name>-coordination/           # local coordination inbox (not a worktree)
    └─ .agent-inbox/
```

Key rules:

- Reserve the `-worktrees/` suffix for actual git worktrees only.
- Use a distinct suffix such as `-coordination/` for local coordination directories that are not worktrees.
- Do not use `-work` as a suffix for coordination directories; it is ambiguous and may be confused with worktrees.
- Coordination directories are local-only and must not be committed to version control.

## Coordination Directory Is Not A Git Workspace

A coordination directory is a file-based communication bus, not a Git workspace. It is intentionally outside the source repository so task files, reports, roster, status board, worktree locks, and event logs can live somewhere that is not part of the project's commit history.

That has three direct consequences for external coding tools:

- The coordination root (for example, `<repo-name>-coordination/.agent-inbox/`) is not a Git repository. External tools that auto-detect Git will fail there, and any tool that tries to run `git -C <coordination-root> worktree add ...` will fail with "not a Git repository".
- External tools must never open the coordination root or its `.agent-inbox/` parent as the project. The project the tool opens must be the assigned `<WORKSPACE_PATH>` (an existing worktree, the primary checkout, or a sandbox), not the coordination directory.
- The coordination root is also not a valid place to put a new worktree. New worktrees created by external workers must live under the same `<projects-root>` parent and use the `-worktrees/` suffix, never the `-coordination/` suffix.

Coordinator preflight before any editable handoff:

- Confirm `<WORKSPACE_PATH>` is a Git worktree: `git -C <WORKSPACE_PATH> rev-parse --is-inside-work-tree` must print `true`.
- Confirm `<WORKSPACE_PATH>` does not end in `<repo-name>-coordination` or `.agent-inbox`.
- If the task file sets `workspace.may_create_worktree: no`, the handoff copy-paste text must include the explicit `Do not create another worktree.` line.

## Avoid This Layout

Do not put worktrees inside the primary repository directory:

```text
<projects-root>/
└─ <repo-name>/
   ├─ src/
   ├─ docs/
   └─ worktrees/
      └─ <task-worktree>/        # avoid
```

## Why

Sibling worktrees reduce these risks:

- Git status pollution: the primary checkout does not show nested task directories as normal files.
- Accidental commits: agents are less likely to stage or commit whole worktree folders.
- Agent context pollution: coding agents, search tools, and long-context readers do not scan duplicate repo copies inside the main repo.
- Build/test pollution: test runners, bundlers, file watchers, and search tools are less likely to traverse duplicate project trees.
- Human confusion: the primary checkout remains the stable baseline; task worktrees are clearly temporary execution areas.
- Cleanup safety: deleting a task worktree is less likely to delete primary project files.

## Role Separation

Treat the primary checkout as the stable baseline:

```text
<repo-name>/
```

Use it for:

- syncing with remote
- reading current main/master state
- final integration review
- final privacy/safety checks
- final release or merge verification

Treat the sibling worktree container as task execution space:

```text
<repo-name>-worktrees/<task-name>/
```

Use it for:

- bounded implementation tasks
- independent review tasks
- runtime smoke tasks
- PR-specific fixes
- temporary branch experiments

## Naming Convention

Use short, scoped names:

```text
<repo-name>-worktrees/docs-examples-quickstart
<repo-name>-worktrees/feature-auth-refactor
<repo-name>-worktrees/review-sample-audit
<repo-name>-worktrees/fix-dashboard-eligibility
```

Branch names should match the task shape:

```text
docs/examples-quickstart
feature/auth-refactor
review/sample-audit
fix/dashboard-eligibility
```

## Creation Template

PowerShell:

```powershell
cd <projects-root>\<repo-name>
git fetch origin
New-Item -ItemType Directory -Force ..\<repo-name>-worktrees | Out-Null
git worktree add ..\<repo-name>-worktrees\<task-name> -b <branch-name> origin/<base-branch>
```

Bash/zsh:

```bash
cd <projects-root>/<repo-name>
git fetch origin
mkdir -p ../<repo-name>-worktrees
git worktree add ../<repo-name>-worktrees/<task-name> -b <branch-name> origin/<base-branch>
```

## Cleanup Template

Remove worktrees through Git first, not by deleting folders manually.

PowerShell:

```powershell
cd <projects-root>\<repo-name>
git worktree list
git worktree remove ..\<repo-name>-worktrees\<task-name>
git branch -d <branch-name>
```

Use `git branch -D` only after explicit user approval.

## Exceptions

A project may use a different layout if:

- the user explicitly chooses a different convention
- the tool/runtime requires a specific path
- the repository is disposable or created only for a one-off task
- the project already has a documented worktree convention

If no project-specific convention exists, use the sibling `<repo-name>-worktrees/` layout.
