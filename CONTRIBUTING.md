# Contributing to Delegator

Thank you for your interest in improving this project. This document explains how to contribute effectively and safely.

## What we welcome

- Documentation improvements, clarifications, and translations.
- Bug reports for broken links, inconsistent terminology, or unclear instructions.
- Proposals for new reference documents that fit the protocol’s scope.
- Examples that demonstrate coordination patterns without exposing private data.
- Schema validator implementations.

## What we do not accept

- Project-specific paths, agent names, model rosters, or secrets.
- Benchmark results or durable claims about fast-changing concrete model names.
- Auto-commit, auto-push, auto-merge, or auto-deploy features.
- Generated task inboxes, worktrees, reports, or agent artifacts.
- Content that exposes author personal toolchains, private repositories, or internal workflows.

## Pull request rules

1. **One concern per PR.** Do not mix documentation fixes with new features in the same PR.
2. **Do not submit private data.** Review your diff before opening the PR. Redact or remove any paths, names, tokens, or internal references.
3. **Update the changelog.** Add an entry to `CHANGELOG.md` under the `[Unreleased]` section. Follow the format described there.
4. **Keep references stable.** If you rename or move a reference document, update all links in `README.md`, `README.zh-CN.md`, `SKILL.md`, and other docs.
5. **Do not modify `SKILL.md` lightly.** `SKILL.md` is the compact core workflow. Changes to it need stronger justification than changes to reference docs.
6. **Do not modify `examples/` without discussion.** Examples are meant to be stable demonstrations. Propose changes in an issue first.
7. **Do not modify `docs/QUICKSTART.md` without discussion.** The quickstart is a minimal smoke test; changes may break new-user onboarding.

## Issue rules

- Use a clear title that describes the problem or proposal.
- For documentation issues, quote the exact text and suggest a replacement.
- For protocol questions, reference the specific file and section.
- For bug reports, include steps to reproduce and expected vs. actual behavior.

## Documentation standards

- Use neutral agent names (e.g., `Reviewer`, `Implementer`, `Smoke-Test`) instead of personal or vendor-specific names.
- Use placeholder paths like `<PROJECT_ROOT>` or `<repo-name>` instead of real project paths.
- Use generic model/tool references instead of concrete model names when possible.
- When concrete model names are necessary, mark them as dated or provisional.
- Keep language consistent with `SKILL.md`. Prefer "task file" over "prompt file", "report file" over "output file", and "coordinator" over "orchestrator".

## Security and privacy

- Do not paste secrets, tokens, or credentials into issues or PRs.
- Do not attach screenshots that contain private data, internal URLs, or real project structures.
- If you discover a security vulnerability, see `SECURITY.md` for how to report it responsibly.

## Fixture conventions

Fixtures are the protocol's source of truth for pass/fail semantics. Every rule in `SKILL.md`, `references/`, and `templates/` should have at least one fixture that exercises it.

### Checked-in fixture trees stay schema-valid

Every fixture tree committed under a pass/valid path in `examples/fixtures/` must pass validation on its own. A fixture that is meant to represent malformed input must live under an explicit invalid/fail path or be generated dynamically by the test runner; do not hide malformed fixtures inside pass/valid trees.

```powershell
python -B scripts/validate-agent-inbox.py --template-mode examples/fixtures/<area>/<case>
```

Prefer generating malformed inputs dynamically at test time (see below). If a checked-in malformed fixture is necessary to test validator failure, place it under an explicit invalid/fail directory and make the expected failure part of the test runner.

### Malformed inboxes are generated dynamically

Negative test cases (invalid frontmatter, missing fields, corrupt trust metadata) must be created inside the test runner's temporary directory, not checked into `examples/fixtures/`. The pattern is:

1. Copy a valid fixture tree into a temp directory.
2. Apply the mutation (delete a field, corrupt a value, inject a contradiction).
3. Run the validator or script against the mutated tree.
4. Assert the expected error or exit code.
5. Temp directory is cleaned up automatically.

This keeps the checked-in fixtures clean and ensures negative cases are reproducible without polluting the repository.

### Mutating tests run on temporary copies

Any test that modifies fixture files (e.g., testing `afc-status.py --write` or archive moves) must copy the fixture tree to a temp directory first. Never modify checked-in fixtures during a test run.

Pattern:

```python
import shutil, tempfile
with tempfile.TemporaryDirectory() as tmp:
    shutil.copytree("examples/fixtures/<area>/<case>", f"{tmp}/inbox")
    # run test against f"{tmp}/inbox"
```

### Tests pass on a clean checkout of the worker's branch

Before a worker claims "tests pass", the tests must pass on a clean checkout:

```powershell
git stash          # or git checkout -- .
python -B <test-command>
git stash pop      # restore working state
```

A test that passes only with uncommitted local changes is not a passing test. The coordinator validates against the committed tree, not the dirty working tree.

### External-format parser fixtures include sanitized real samples

When adding parsers for external formats (token logs, usage exports, provider-specific outputs), include at least one fixture based on real data with private fields redacted. Synthetic-only fixtures miss edge cases that real data exposes.

Redaction rules:
- Replace real paths with `<PROJECT_ROOT>` or `<repo-name>`.
- Replace real agent names with neutral labels (`Worker1`, `Reviewer`).
- Replace real model names with generic labels (`<model-name>`).
- Replace tokens, API keys, and account IDs with `<REDACTED>`.
- Preserve the structural shape (field order, nesting, line count).

Tag the fixture source in a comment at the top of the file:

```markdown
<!-- Source: sanitized from <provider> export, 2026-06-12 -->
```

## Development workflow

1. Fork the repository.
2. Create a feature branch from `master`.
3. Make your changes.
4. Run a local diff review to ensure no private data is included.
5. Update `CHANGELOG.md`.
6. Open a PR with a clear description and link to any related issues.

## Code of conduct

Be respectful, constructive, and concise. Assume good intent. Focus on the protocol, not the person.
