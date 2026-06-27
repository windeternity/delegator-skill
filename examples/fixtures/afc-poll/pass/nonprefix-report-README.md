**Fixture: nonprefix-report (pass)**

- One task (`task-cache-test-Implementer.md`) and one report (`cache-test-Implementer-result.md`).
- The report does NOT start with `report-` but has `schema: agent-file-coordination/report` in its frontmatter.
- No pre-existing state file (first run).
- Expected: exit 0, stdout contains `next_action: coordinator should review`, the non-prefixed report file is detected as a new report, state file is created with `cache-test-Implementer-result.md` recorded.
