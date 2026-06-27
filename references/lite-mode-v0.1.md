# Lite Mode v0.1

Status: active, narrow exception selected only by `afc-route.py`.

## Purpose

LITE satisfies an explicit requirement to use one external worker without
paying the full task/status/event/verdict protocol. It is not the default for
small work: small work normally routes `DIRECT`.

## Required Conditions

All conditions must hold:

- an external worker is explicitly required;
- estimated direct effort is at least 15 minutes;
- exactly one independent workstream;
- no semantic behavior change;
- one expected report/verdict round;
- no high-risk, destructive, network, secret, schema, authority, permission,
  state-machine, or production change;
- the allowed file surface is explicit and has no lock conflict.

If any condition fails, use the route result: normally `DIRECT`, `FULL`, or
`SPLIT`. Workers cannot elect LITE themselves.

## Execution

```powershell
python -B scripts\afc-lite.py `
  --agent <AGENT_NAME> `
  --workspace <PROJECT_PATH> `
  --task "<ONE_BOUNDED_TASK>" `
  --allow-files "<EXPLICIT_FILES>" `
  --validation "<ONE_COMMAND_OR_NONE>" `
  --language zh `
  --estimated-direct-minutes <N> `
  --external-worker-required yes `
  --semantic-change no
```

The command reruns the route gate and prints a compact handoff. It creates no
`.agent-inbox/`, task, status, event, report, or verdict files.

## Boundaries

- Coordinator retains final accept/reject authority.
- Worker may modify only the named files.
- Commit, push, destructive actions, network access, and scope expansion remain
  denied unless separately authorized by the user outside LITE.
- The worker reply contains only changed files, validation result, and blockers.
- The coordinator checks the diff once. Escalate to FULL if semantic uncertainty
  or a repair loop appears.

## Examples

Appropriate: update one documented version string, normalize formatting in one
allowlisted file, rename a non-public local identifier without behavior change.

Not appropriate: add validation behavior, change an API or schema, repair a
state machine, install a dependency, edit permissions, or split a small task
among several workers.

## History

- v0.1 (2026-06-12): proposal.
- v0.1 active (2026-06-14): promoted with a deterministic route gate and
  no-inbox `afc-lite.py` implementation after the P2B cost finding.
