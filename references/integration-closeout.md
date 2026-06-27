# Integration Closeout

This reference defines the canonical integration order, file-ownership rules, staged-file allowlist, validation snapshot policy, and temp-artifact cleanup for coordinated multi-agent work. Use it when merging worker branches into the primary checkout or closing out a coordination sprint.

## Canonical Integration Order

Follow this order for every integration. Skipping or reordering steps risks silent data loss or merge conflicts that are hard to diagnose.

1. **Preflight — primary checkout clean and on expected branch.**
   Run in the primary checkout:

   ```powershell
   git status --short
   git branch --show-current
   ```

   Both must be clean and on the expected base branch (`master` / `main`). If dirty, resolve before proceeding.

2. **Fetch and inspect the worker branch.**

   ```powershell
   git fetch origin
   git log --oneline origin/<worker-branch> --not origin/<base-branch>
   ```

   Confirm the commit range matches the task scope. If the worker committed files outside `locked_files_or_areas`, flag before merging.

3. **Preflight — staged-file allowlist check.**
   Before `git merge` or `git cherry-pick`, confirm the incoming diff touches only files the task was authorized to modify. See § Staged-File Allowlist below.

4. **Merge or cherry-pick.**

   ```powershell
   git merge --no-ff origin/<worker-branch>   # preferred for full branch history
   # or
   git cherry-pick <commit-range>              # for squashed or selective picks
   ```

5. **Post-merge validation.**
   Build one risk-weighted validation plan after source convergence, then run it
   once. The Evidence Ladder task-shape minimum is the floor; risk may raise but
   never lower it. Group surfaces by shared validation strategy instead of
   verifying every file independently. See `references/decision-rubric.md`
   § Risk-Weighted Verification Budget. Do not skip this step — a green worker
   report does not guarantee a green merge.

6. **Post-merge — dirty-tree check.**

   ```powershell
   git status --short
   ```

   The tree must be clean after validation. If validation left generated files, clean them per § Temp Artifact Cleanup.

7. **Record the verdict.**
   Update the task's status in `.agent-inbox/STATUS.md` and write the coordinator verdict. Only then consider `git push`.

## Authoritative-File Ownership

Each file in the repository has exactly one authoritative owner at integration time. Ownership is determined by the `locked_files_or_areas` field in the task frontmatter.

| Owner | Files | Rule |
|-------|-------|------|
| Primary checkout (coordinator) | `SKILL.md`, `templates/`, `.agent-inbox/` | Only the coordinator merges changes to these files. Workers propose via reports; the coordinator applies. |
| Worker branch | Files in the worker's `locked_files_or_areas` | The worker owns these for the duration of the task. No other worker or the coordinator should edit them concurrently. |
| Shared (read-only) | `references/`, `scripts/`, `examples/` | Workers may read but must not edit unless their task explicitly grants `modify_source: yes` for a specific file. |

When two tasks claim overlapping `locked_files_or_areas`, the lock-intersection check in the task file must have resolved the overlap before assignment. If a conflict slips through, stop and resolve with the task owners before merging.

## Staged-File Allowlist

Before merging a worker branch, confirm the incoming diff touches only files the task authorized.

**Check command** (run in the primary checkout after fetching):

```powershell
git diff --name-only origin/<base-branch>..origin/<worker-branch>
```

**Validation rule**: every file in the output must appear in the task's `locked_files_or_areas` (or be a file the task explicitly allowed via `modify_source: yes`). If a file appears that was not authorized:

1. Do not merge.
2. Report the unauthorized file in the coordinator verdict.
3. Ask the worker to explain or revert the change.

This check catches accidental edits (wrong directory, autocomplete errors, tool-generated files) before they enter the main branch.

## Dirty-Tree vs Committed-Tree Validation

Worker reports sometimes claim "all tests pass" based on in-memory or uncommitted changes. The coordinator must validate against the **committed tree**, not the dirty working tree.

| Scenario | Validation approach |
|----------|---------------------|
| Worker reports test results from their worktree | Re-run the same tests on the committed state: `git stash && <test-command> && git stash pop` |
| Worker committed all changes | Validate directly on the merged commit. |
| Worker left uncommitted changes | Stash, validate, pop. If the stash pop conflicts, the worker's changes were not self-consistent. |

Never accept a worker's self-reported test output as proof. The coordinator or a trusted script must reproduce the result.

## Temp Artifact Cleanup

Coordination work generates temporary artifacts: worktrees, stash entries, validation logs, partial merge states. Clean them up after integration.

### Checklist

- [ ] Remove merged worker worktrees:

  ```powershell
  git worktree list
  git worktree remove <path-to-merged-worktree>
  ```

- [ ] Delete merged worker branches (local and remote):

  ```powershell
  git branch -d <worker-branch>
  git push origin --delete <worker-branch>   # only if remote tracking exists
  ```

- [ ] Drop stash entries used during validation:

  ```powershell
  git stash list
  git stash drop stash@{N}
  ```

- [ ] Remove validation logs or temp files left by scripts (check `scripts/` output directories).

- [ ] Confirm `git status --short` is clean in the primary checkout.

### Do Not Delete

- `.agent-inbox/` files for tasks that are still `ACTIVE` (see `references/archive-policy-v0.1.md`).
- Archived task/report files — move them to `.agent-inbox/archive/<YYYY-MM>/` per the archive policy, do not delete.
- `WORKTREE_LOCKS.md` entries for locks that are still `ACTIVE`.

## Windows-Safe Cleanup Notes

Windows file-system behavior creates specific cleanup hazards:

| Hazard | Mitigation |
|--------|------------|
| `git worktree remove` fails with "directory not empty" | Close all editors and terminals that have the worktree as a working directory. Use `git worktree remove --force` only after confirming no unsaved work. |
| Long path names exceed 260-character limit | Use `git config core.longpaths true` before worktree operations. Prefer short sibling names (e.g., `sprint10-j5` not `agent-file-coordination-skill-worktrees-sprint10-j5-integration-closeout`). |
| File locks from background processes (antivirus, indexers) | Wait and retry. If persistent, identify the locking process via `handle.exe` or `Process Explorer` before forcing deletion. |
| Stale worktree entries point to deleted folders | Run `git worktree prune` to clean the worktree list. |
| PowerShell `Remove-Item -Recurse` fails on hidden `.git` files | Use `git worktree remove` instead of manual folder deletion. The `.git` file in a worktree is a pointer file, not a directory — `git worktree remove` handles it correctly. |

**Rule**: always use `git worktree remove` and `git branch -d` for cleanup. Never delete worktree folders manually — Git tracks worktree state internally, and manual deletion leaves stale entries that cause confusing errors later.

## Integration Closeout Summary

For quick reference, the full closeout sequence in one block:

```text
1. git status --short && git branch --show-current   # primary clean?
2. git fetch origin && git log --oneline <range>      # inspect worker branch
3. git diff --name-only <range>                       # staged-file allowlist
4. git merge --no-ff origin/<worker-branch>           # merge
5. <one risk-weighted validation plan>                # post-merge validation
6. git status --short                                 # dirty-tree check
7. Update STATUS.md + verdict                         # record
8. git worktree remove + git branch -d                # cleanup
```
