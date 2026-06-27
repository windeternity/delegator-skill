# Delegated Release Operations

This reference defines the protocol path for delegating bounded git, PR, CI, and review-response chores to a **Release-Operator** worker. It does not change schema identifiers, lifecycle states, or default permissions. It is an on-demand read for coordinators who need to delegate release chores without turning ordinary workers into coordinators.

## Purpose

Ordinary workers are default-deny for `commit`, `push`, `open PR`, `merge PR`, `respond to review`, and `delete branch`. This reference defines a specialized worker role — **Release-Operator** — that may perform these actions when the coordinator grants explicit authorization through the task's `Permission Scope`.

This is a **CAL-1/CAL-2 optimization**: the coordinator delegates bounded release chores to a known-capable worker instead of performing them manually. It is not C6/CAL-3 (auto-dispatch of workers); the user or coordinator still relays the handoff.

## Non-Goals

- Do not grant ordinary workers default commit/push/merge permission.
- Do not auto-dispatch Release-Operators (that is C6/CAL-3, which remains deferred).
- Do not change `schema_version`, lifecycle states, or frontmatter fields.
- Do not bypass worktree locks, evidence review, or coordinator final authority.
- Do not delegate merge authority in this protocol version; merge remains coordinator/user authority.

## Roles

### Release-Operator

A worker authorized to perform bounded git/gh operations for a specific task. The Release-Operator is a task-only worker with an expanded `commit_push` scope for that task only.

**Hard gates:**

1. **Explicit authorization required.** The task frontmatter must set `commit_push: approved` (not `no` or `ask`). A lite-mode handoff that says "commit" is not sufficient for Release-Operator; a full task file is required.
2. **Scoped to the task's locked files.** The Release-Operator may only commit changes within `locked_files_or_areas`. Changes outside that scope must be reverted before commit.
3. **Staged-file allowlist enforced.** Before committing, the Release-Operator must verify that `git diff --name-only` shows only files in the task's `locked_files_or_areas`. If unauthorized files appear, stop and report.
4. **No force-push, no branch deletion, no deploy.** These remain `destructive_actions: no` even for Release-Operators unless the task explicitly sets `destructive_actions: approved` with user-level approval.
5. **Report before commit.** The Release-Operator must write the report file first, then commit. The report must include the exact commit message, file list, and validation commands. The coordinator reviews the report before the commit is pushed.
6. **No self-merge.** The Release-Operator may open a PR but may not merge it. Merge authority remains with the coordinator or user.

### Integrator

The coordinator's role during merge/integration. Defined in `references/integration-closeout.md`. The Integrator:

1. Runs preflight checks (primary clean, branch correct).
2. Inspects the worker branch diff against the staged-file allowlist.
3. Runs post-merge validation.
4. Records the verdict.

The Integrator is always the coordinator, never a worker.

### Review-Responder

A worker authorized to respond to PR review comments (address feedback, push fixes, mark comments resolved). The Review-Responder is a Release-Operator variant with additional constraints:

**Hard gates:**

1. **Scoped to one PR.** The Review-Responder operates on a single PR identified by URL or number. The task must name the PR.
2. **Fix-only scope.** The Review-Responder may only push commits that address review comments. Feature additions, refactors, or unrelated fixes are forbidden.
3. **No merge authority.** Same as Release-Operator.
4. **Evidence required.** The report must list each review comment addressed, the fix applied, and the commit hash. The coordinator verifies against the PR's review thread.

## Permission Model

| Action | Ordinary Worker | Release-Operator | Review-Responder |
|--------|----------------|-----------------|------------------|
| Read project files | allowed | allowed | allowed |
| Modify source (in scope) | `modify_source: yes` | `modify_source: yes` | `modify_source: yes` |
| Commit | blocked | `commit_push: approved` | `commit_push: approved` |
| Push | blocked | `commit_push: approved` | `commit_push: approved` |
| Open PR | blocked | `commit_push: approved` | blocked |
| Respond to PR review | blocked | blocked | `commit_push: approved` + PR scoped |
| Merge PR | blocked | blocked | blocked |
| Force push | blocked | blocked | blocked |
| Delete branch | blocked | blocked | blocked |
| Deploy | blocked | blocked | blocked |

**Default-deny preserved.** Every git/gh action remains blocked unless the task frontmatter explicitly grants it. "Not forbidden" is not permission.

## Preflight Evidence Requirements

Before performing any git/gh operation, the Release-Operator or Review-Responder must collect and report:

### Release-Operator Self-Check

The Release-Operator must complete this checklist before committing. Every item must appear in the report:

1. **Staged-file allowlist.** `git diff --name-only` shows only files in `locked_files_or_areas`. If any file outside the allowlist appears, stop and report the discrepancy before proceeding. Do not revert files by default; the coordinator decides whether to revert, amend, or re-scope.
2. **Change summary.** `git diff --stat` for the coordinator's key-focused review.
3. **Commit message.** Exact message in conventional format (`<type>(<scope>): <description>`, ≤72-char subject). Report the message verbatim.
4. **Validation commands and results.** Run the project's minimum validation set. Report exact commands and exit codes.
5. **Branch and history.** `git branch --show-current` and `git log --oneline -5` confirm the branch matches the task and no unrelated commits are present.
6. **Report completeness.** The report file must be written before any commit. It must include: changed files list, exact commit message, validation commands + results, and any discrepancies found during self-check.

### Review-Responder Self-Check

For review-response tasks, the self-check adds:

1. **PR scope.** The task names one PR. All commits must address comments on that PR only.
2. **Comment-to-fix mapping.** Report each review comment addressed, the fix applied, and the commit hash. Unresolved or deferred comments must be listed explicitly.
3. **Fix-only scope.** Feature additions, refactors, or unrelated fixes are forbidden. If the worker finds an unrelated issue, it must be reported as a finding, not fixed inline.

### Merge/PR Preflight

| Evidence | Source | Purpose |
|----------|--------|---------|
| `git status --short` | worktree | Confirm clean tree before commit |
| `git diff --name-only` | worktree | Staged-file allowlist check |
| `git diff --stat` | worktree | Summary of changes for key-focused review |
| `git log --oneline -5` | worktree | Confirm commit history matches task scope |
| `git branch --show-current` | worktree | Confirm correct branch |

### PR Creation Preflight

| Evidence | Source | Purpose |
|----------|--------|---------|
| PR title and body | gh CLI or draft | Confirm PR scope matches task |
| Changed files list | `gh pr diff --name-only` | Staged-file allowlist for PR |
| CI status (if available) | `gh pr checks` | Confirm CI passed before requesting review |

### Review-Response Preflight

| Evidence | Source | Purpose |
|----------|--------|---------|
| Review comments addressed | PR thread | Map each comment to a fix |
| Commit hashes for fixes | `git log --oneline` | Verify each fix is a separate commit |
| Remaining unresolved comments | PR thread | Confirm all comments addressed or explicitly deferred |

## Task File Requirements

A Release-Operator or Review-Responder task file must include:

```markdown
## Permission Scope
- commit_push: approved
- destructive_actions: no   # or approved with user approval
```

And in the task body:

```markdown
## Release Operations Scope
- Target branch: <branch>
- Allowed operations: commit, push, open PR  # or: respond to review
- PR URL/number: <if review-response>
- Staged-file allowlist: <locked_files_or_areas>
```

The coordinator must complete the standard J3 lock-intersection check before assigning.

## Coordinator Review

When reviewing a Release-Operator report, the coordinator performs **key-focused review** — inspecting the decision-critical evidence, not re-reading the full diff. This is the coordinator's risk-management responsibility; it replaces the manual full-code rework that would otherwise consume coordinator quota.

### What the coordinator checks

1. **Staged-file allowlist.** Does the worker's `git diff --name-only` output match `locked_files_or_areas` exactly? Any file outside the allowlist is a scope violation — downgrade to `RED` or `NEEDS_FIX`.
2. **Commit message.** Does it match the task scope? Is it conventional format? Is the subject ≤72 characters?
3. **Validation evidence.** Did the worker run the required validation commands? Do exit codes match claimed results?
4. **PR scope (if applicable).** Does the PR title/body match the task? Are there unrelated changes in the PR diff?
5. **Review-response completeness (if applicable).** Are all review comments addressed? Are fixes scoped to the review? Are unresolved comments listed?
6. **High-risk diff spots.** If the diff touches security-sensitive, public-API, or infrastructure files, open those specific files for targeted inspection. Do not open the full diff unless a specific concern arises.
7. **Unresolved risks.** Does the report's "Remaining Risk" section identify genuine risks, or is it empty when risks exist?

### What the coordinator does NOT do

- **No full default reread.** The coordinator does not read every changed file end-to-end. The report's evidence summary, allowlist, and validation results are the primary review surface.
- **No default full validation rerun.** The coordinator trusts the worker's reported validation commands and exit codes as the primary evidence. However, the coordinator retains authority to rerun cheap or final release gates (e.g., `git diff --check`, `audit-docs.py`, `check-public-safety.py`), targeted commands that verify specific suspicious claims, or spot-checks when the report's evidence looks inconsistent. This is targeted verification, not a full re-execution of the worker's build.
- **No re-implementing the fix.** The coordinator reviews the evidence and issues a verdict. If the fix is wrong, the coordinator issues `NEEDS_FIX` with a specific instruction — not a manual rewrite.

### Review escalation

If the summary raises concerns (allowlist mismatch, missing validation, suspicious commit message, high-risk diff spots), the coordinator may:

- Open specific files for targeted inspection.
- Request the worker provide additional evidence.
- Downgrade to `PARTIAL` or `RED` with a specific explanation.
- Route to an independent reviewer if the risk warrants it.

## Relationship to Existing References

| Reference | Relationship |
|-----------|-------------|
| `references/action-permission-matrix.md` | Adds Release-Operator and Review-Responder rows to the permission table |
| `references/worker-brief.md` | Adds Release-Operator behavior rules and evidence requirements |
| `references/integration-closeout.md` | Defines the Integrator role; Release-Operator produces the PR, Integrator merges it |
| `references/lite-mode-v0.1.md` | Lite mode may grant commit for mechanical tasks; Release-Operator is the full-protocol path for release chores |
| Release vs. CAL-3 boundary | Release-Operator is CAL-1/CAL-2 delegation of release chores; C6/CAL-3 auto-dispatch is a separate concern |

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| Release-Operator pushes unreviewed code | High | Report-before-commit; coordinator reviews before push is allowed |
| Scope creep: worker commits files outside locked area | Medium | Staged-file allowlist enforced by the worker and verified by the coordinator |
| Review-Responder addresses unrelated comments | Medium | Fix-only scope; report must map each comment to a fix |
| Release-Operator granted to untrusted worker | High | Only known-capable workers on the fixed roster; full task file required |
| Coordinator forgets to review before push | Medium | Report-before-commit is a hard gate; coordinator must explicitly approve |

## Version Policy

This document follows the project's `CHANGELOG.md` conventions. Changes to the Release-Operator permission model require a coordinator review and a new version entry.
