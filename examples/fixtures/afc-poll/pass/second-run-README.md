# Fixture: second-run (pass)

## Setup
- One task file (`task-poll-b.md`) and two report files.
- `report-Worker2-poll-b.md` — already recorded in the state file (mtime `2026-06-07T18:00:00Z`).
- `report-Worker3-poll-c.md` — not in the state file (new arrival).
- Pre-existing `.afc-poll-state.json` records only the old report.

## Expected command
```
python -B scripts/afc-poll.py examples/fixtures/afc-poll/pass/second-run
```

## Expected result
- Exit code: 0
- stdout contains `next_action: coordinator should review` only for `report-Worker3-poll-c.md`.
- `report-Worker2-poll-b.md` does NOT appear in next_actions (unchanged).
- State file is updated to include both reports.
