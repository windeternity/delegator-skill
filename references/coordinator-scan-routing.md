# Coordinator Scan Routing

Use this reference when a coordinator needs project state, code context, or
evidence before routing work.

## Rule

The coordinator should not perform broad source scans as a default move. Broad
`rg`, recursive file reads, and exploratory directory sweeps are expensive
because their outputs enter the coordinator thread and are likely to be re-fed
on later turns.

Choose one of these bounded paths instead:

1. **Read an existing snapshot or summary.** Prefer
   `scripts/afc-snapshot.py --brief <INBOX>` for coordination state and
   `scripts/afc-status.py --summary-only <INBOX>` for task/report status.
2. **Read one known file or section.** If the needed artifact is already known,
   open only that file or line range.
3. **Delegate read-only exploration.** For code discovery, assign a bounded
   read-only task and ask for a compressed packet: files inspected, key facts,
   uncertainties, and recommended next file(s). The worker should not paste full
   logs, full diffs, or broad search output.

## When Coordinator Scanning Is Allowed

Coordinator-side scanning is appropriate for:

- mechanical Git/status checks;
- verifying a named file, fixture, report, or validation output;
- targeted searches tied to one hypothesis or one symbol;
- final validation after worker evidence has narrowed the surface.

## Read-Only Exploration Packet

When delegating exploration, require a compact report:

```text
Scope searched:
Files/commands inspected:
Findings:
Likely next files:
Uncertainties:
No edits made:
```

The packet should be enough for the coordinator to decide the next bounded task
without importing the worker's full search transcript.

## Anti-Patterns

- Re-running repository-wide `rg` searches every coordinator turn.
- Reading whole source trees to decide whether a worker task is needed.
- Pasting raw command output into verdicts or handoffs.
- Treating an open-ended "continue" prompt as permission to keep expanding
  local investigation.

