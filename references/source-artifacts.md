# Source Artifacts

Status: active guidance.

Source artifacts are upstream evidence that explains what a task is based on.
They are optional metadata, but they are useful for MOA and protocol work where
the decision surface must stay stable across workers.

## Field

Use a short list of paths or identifiers:

```yaml
source_artifacts:
  - docs/WHEN_TO_USE_AFC.md
  - references/delegation-routing-v1.md
  - issue:123
```

Prefer paths over pasted content. Long context belongs in source files or
artifacts, not in the task body.

## Supported Sources

Common source artifacts include:

- PRD or product brief;
- design document;
- OpenSpec proposal, specs, design, or tasks;
- GitHub issue or PR;
- benchmark case record;
- prior coordinator verdict;
- existing task or report file.

## Rules

- Source artifacts are evidence, not authority over the user or task file.
- A worker may quote or summarize source artifacts only within its permission
  scope.
- A report should cite the source artifact path when a finding depends on it.
- If source artifacts conflict with the task file, the task file wins and the
  report should flag the conflict.
- Do not include secrets, local account identifiers, or private workspace paths
  in reusable public examples.

## OpenSpec Mapping

When an OpenSpec-style upstream exists, reference it instead of duplicating it:

```yaml
source_artifacts:
  - openspec/changes/<change>/proposal.md
  - openspec/changes/<change>/design.md
  - openspec/changes/<change>/tasks.md
  - openspec/changes/<change>/specs/
```

Delegator consumes these as inputs. It does not own the spec lifecycle.

