# Fixture: fresh-inbox (pass)

## Setup
- One task file (`task-poll-a.md`) and one report file (`report-Worker1-poll-a.md`).
- No pre-existing state file (first run).
- No pre-existing STATUS.md (afc-status.py will create it).

## Expected command
```
python -B scripts/afc-poll.py examples/fixtures/afc-poll/pass/fresh-inbox
```

## Expected result
- Exit code: 0
- stdout contains `next_action: coordinator should review` for the report.
- State file `.afc-poll-state.json` is created inside the inbox.
- STATUS.md is created by the afc-status.py subprocess.
