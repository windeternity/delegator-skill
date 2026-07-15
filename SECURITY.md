# Security Policy

This document describes security risks related to Delegator and how to report vulnerabilities.

## Security Boundaries

Delegator is a coordination protocol, not a sandbox. It helps with specific safety
gates but does not guarantee protection against all threats.

| Delegator helps with | Delegator does not guarantee |
|---|---|
| Task/report permission boundaries | OS-level sandboxing or process isolation |
| Worker report distrust and evidence grading | Worker honesty or model alignment |
| Common secret/path publication checks | All semantic data leak prevention |
| Validation command guardrails and timeout protection | Arbitrary shell safety proof |
| CAL-3 CLI binding verification and explicit dispatch | Provider, tool, or runtime correctness |
| Public export hygiene and forbidden directory scanning | Perfect full-history or side-channel secrecy |

These boundaries define what the protocol is designed to protect against. If
a risk falls outside these boundaries, you must add additional safeguards or
choose not to use Delegator for that task.

## Scope

This project is a **coordination protocol**, not an agent runtime. It does not execute code, manage credentials, or perform network operations. However, the protocol itself can be misused or attacked if coordinators and agents do not follow its guardrails.

## Prompt-injection risk

### What it is

A malicious or compromised file, webpage, log, or dependency may contain instructions designed to override the coordinator’s rules, leak secrets, or trigger unauthorized actions.

### How this protocol mitigates it

- **Task file outranks report content.** The original task file and explicit user authorization take precedence over any instructions found in agent reports or external sources.
- **Default deny.** Actions not explicitly allowed in the task file are blocked. This includes commit, push, merge, deploy, delete, and permission changes.
- **Trust levels.** Reports are graded `self_claim`, `referenced`, `reproduced`, `independent_reviewed`, or `blocked_or_suspicious`. The coordinator must verify evidence before acting.
- **Prompt-injection red flags.** The protocol lists specific suspicious patterns (ignore previous rules, reveal secrets, skip validation, trust without evidence, etc.) that should trigger `RED` or manual review.

### What users must do

- Never paste untrusted content into task files without review.
- Treat agent reports as untrusted inputs until evidence is verified.
- Do not follow instructions from reports, logs, or webpages that conflict with the task file or user authorization.
- Review all commands suggested in reports before executing them.

## Secrets handling

### What must never happen

- Secrets, tokens, passwords, or private credentials must never be written into task files, report files, status boards, or `.agent-inbox/` files.
- Secrets must never be printed into agent reports or terminal output shared with other agents.
- `.env` files and credential stores must never be read by agents unless explicitly authorized and redacted.

### What the protocol requires

- Task files include a guardrail: `Do not print secrets or private data.`
- Report files include a guardrail confirmation: `secrets/private data printed: no`.
- If a report contains a secret leak, the coordinator must mark the result `RED` unless the leak is harmless and contained.

## Validation command execution boundary

Some task files may declare a `validation_command`. For high-risk tasks, `afc-intake.py` can re-run that command in the declared workspace as coordinator-side verification. This is a trusted-command path: the command is expected to be authored by the coordinator in the task file, not supplied by a worker report or copied from untrusted logs, webpages, dependency output, or generated files.

Treat task files as privileged coordination contracts. Do not paste unreviewed shell commands into `validation_command`; prefer simple project-local checks such as targeted tests, `git diff --check`, or a reviewed script already in the repository. If the command would install dependencies, contact production, read secrets, mutate system settings, deploy, push, delete, or run broad shell cleanup, require explicit user approval and a dedicated task boundary before running it.

The current implementation includes timeout and destructive-pattern checks, but those are defense-in-depth, not a sandbox. Future protocol work should prefer declarative validation profiles or an allowlisted command catalog for common gates.

## Reporting security issues

If you discover a security vulnerability in the protocol, its documentation, or its recommended tooling:

1. **Do not open a public issue.** Public issues may expose the vulnerability before a fix is ready.
2. Report privately using GitHub's [Private Vulnerability Reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) for this repository (Security tab → "Report a vulnerability"). Do not disclose details in public channels until a fix is available.
3. Include:
   - A description of the vulnerability.
   - Steps to reproduce or exploit it.
   - The impact if exploited.
   - Any suggested mitigation.
4. Allow reasonable time for review and response before public disclosure.

## Security-related references

For detailed guidance, see:

- `references/report-trust-and-prompt-injection.md` — trust levels and injection handling
- `references/action-permission-matrix.md` — default allow/deny matrix for agent actions
- `references/decision-rubric.md` — scoring rubric that includes safety/privacy as a dimension

## Acknowledgments

We will publicly acknowledge responsible disclosures in `CHANGELOG.md` unless the reporter requests anonymity.
