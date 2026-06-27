# Assignment Quality Checklist

Status: active guidance for coordinator-authored tasks.

Use this checklist before dispatching a `FULL`, `LITE`, or MOA task. It keeps
task files small, testable, and safe for worker execution.

## Required Qualities

A task should have:

- exact read paths or source artifacts;
- exact editable paths, or `modify_source: no`;
- explicit forbidden paths or areas when confusion is likely;
- one assigned agent;
- one report path;
- at most five acceptance criteria;
- one validation tier and, when useful, one validation command;
- no placeholders such as `TBD`, `fill later`, or `decide yourself`;
- clear permission scope for file edits, commands, network, commit/push, and
  destructive actions.

## MOA-Specific Checks

For `moa_review` and `moa_design`:

- default to `modify_source: no`;
- use the same decision surface across candidate tasks;
- keep candidate outputs independent;
- assign all candidates to the same `comparison_group`;
- create a separate `moa_synthesis` task when comparison is needed.

For `moa_patch`:

- use dedicated worktrees;
- do not assign overlapping editable locks;
- require each candidate to report changed paths and validation evidence;
- select one candidate only after synthesis and coordinator review.

## Stop Conditions

Do not dispatch the task if:

- the expected report needs more than two repair rounds;
- the body needs more than 4 KB of inline context;
- the worker must infer permission from prose;
- source edits are allowed but locks are unclear;
- validation is required but no feasible validation tier is named;
- the task requires commit, push, deploy, secrets, production, or destructive
  actions without explicit user authorization.

## Pre-Dispatch Review

Before sending the handoff, check:

```text
route evidence exists
permission_scope matches body
workspace mode matches edit permission
report_path is unique
acceptance criteria are observable
source artifacts are paths, not pasted dumps
worker cannot self-approve
```

