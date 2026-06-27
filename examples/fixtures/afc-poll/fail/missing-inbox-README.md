# Fixture: missing-inbox (fail)

## Setup
- The `nonexistent-dir` directory does not exist.

## Expected command
```
python -B scripts/afc-poll.py examples/fixtures/afc-poll/fail/missing-inbox/nonexistent-dir
```

## Expected result
- Exit code: 1
- stderr contains `directory not found`.
