# afc-init fixtures

This directory contains fixtures and a test runner for the
`afc-init.{ps1,sh}` bootstrap scripts.

## Layout

- `refuse-existing/` — a project root whose `.agent-inbox/` already
  contains one of the target files. Used to verify that the scripts
  refuse to overwrite without an explicit `--force` / `-Force` flag.
- `run-tests.py` — Python-based test runner that exercises both
  scripts in headless mode against a fresh temp working directory.
- `README.md` — this file.

## Usage

From the repository root:

```text
python -B examples/fixtures/afc-init/run-tests.py
```

The runner uses a fixed `--created-at` of `2026-06-08` so its output
is deterministic and fixture-stable.

## What the Runner Exercises

For each of the two scripts (`afc-init.sh`, `afc-init.ps1`):

1. Create-inbox-from-scratch: the script writes the four
   `.agent-inbox/` files with no pre-existing state.
2. Re-run without `--force` exits nonzero and does not modify files.
3. Run with `--force` overwrites the existing files.
4. Generated `AGENT_ROSTER.md`, `STATUS.md`, `WORKTREE_LOCKS.md`, and
   `events.jsonl` all pass `scripts/validate-agent-inbox.py --template-mode`.
5. Failure paths:
   - missing project root exits nonzero
   - invalid date format exits nonzero
   - unknown flag exits nonzero
6. `--help` exits zero and prints usage.

## Shell Portability Note

The `bash` interpreter on this Windows machine is WSL2, which mounts
the Windows drive at `/mnt/<drive>/<path>`. The runner converts
Windows paths to WSL paths automatically. On a non-WSL Git Bash host
the path style would be `/<drive>/<path>`. If the runner cannot find
bash or pwsh, it skips that script with a clear note.
