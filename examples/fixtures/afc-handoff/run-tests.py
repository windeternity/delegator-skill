#!/usr/bin/env python3
"""Test runner for afc-handoff.py fixtures.

Usage:
    python -B examples/fixtures/afc-handoff/run-tests.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "afc-handoff.py")
SCRIPT = os.path.normpath(SCRIPT)

BASE = os.path.dirname(os.path.abspath(__file__))
PASS_DIR = os.path.join(BASE, "pass")
BASIC = os.path.join(PASS_DIR, "basic")

FIXED_DATE = "2026-06-14"


def run(args, expect_exit=0, label=""):
    """Run afc-handoff.py with given args. Returns (ok, stdout, stderr)."""
    cmd = [sys.executable, "-B", SCRIPT] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    ok = result.returncode == expect_exit
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label} (exit={result.returncode}, expected={expect_exit})")
    if not ok:
        print(f"    stdout: {result.stdout[:500]}")
        print(f"    stderr: {result.stderr[:500]}")
    return ok, result.stdout, result.stderr


def test_help():
    """--help exits 0 and names the script."""
    ok, stdout, stderr = run(["--help"], expect_exit=0, label="--help")
    if "afc-handoff" not in stdout.lower():
        print(f"    FAIL: expected 'afc-handoff' in stdout, got: {stdout[:200]}")
        ok = False
    return ok


def test_basic_sections():
    """Basic inbox renders all handoff sections and the active task."""
    ok, stdout, stderr = run(
        ["--date", FIXED_DATE, BASIC],
        expect_exit=0,
        label="basic-sections",
    )
    expected = [
        f"New Thread Handoff — {FIXED_DATE}",
        "## Current Roster",
        "## Active Tasks",
        "## Recent Events",
        "## Blockers",
        "## Next Action",
        "## Guardrails",
        "alpha",
    ]
    for token in expected:
        if token not in stdout:
            print(f"    FAIL: expected '{token}' in output, got: {stdout[:400]}")
            ok = False
    return ok


def test_roster_rows_included():
    """Roster table rows are embedded from AGENT_ROSTER.md."""
    ok, stdout, stderr = run(
        ["--date", FIXED_DATE, BASIC],
        expect_exit=0,
        label="roster-rows",
    )
    if "Coordinator Authority" not in stdout:
        print(f"    FAIL: expected roster header row, got: {stdout[:400]}")
        ok = False
    if "Worker" not in stdout:
        print(f"    FAIL: expected roster row for Worker, got: {stdout[:400]}")
        ok = False
    return ok


def test_recent_events_summarized():
    """Recent events from events.jsonl appear in the handoff."""
    ok, stdout, stderr = run(
        ["--date", FIXED_DATE, BASIC],
        expect_exit=0,
        label="recent-events",
    )
    if "TASK_DISPATCHED" not in stdout:
        print(f"    FAIL: expected recent event 'TASK_DISPATCHED', got: {stdout[:400]}")
        ok = False
    return ok


def test_next_action_review():
    """Active task with a report yields a review next-action hint."""
    ok, stdout, stderr = run(
        ["--date", FIXED_DATE, BASIC],
        expect_exit=0,
        label="next-action-review",
    )
    if "Review the report for 'alpha'" not in stdout:
        print(f"    FAIL: expected review hint for alpha, got: {stdout[:400]}")
        ok = False
    return ok


def test_deterministic():
    """Same inputs and --date produce byte-identical output."""
    ok1, out1, _ = run(["--date", FIXED_DATE, BASIC], expect_exit=0, label="deterministic-1")
    ok2, out2, _ = run(["--date", FIXED_DATE, BASIC], expect_exit=0, label="deterministic-2")
    ok = ok1 and ok2
    if out1 != out2:
        print("    FAIL: output is not deterministic across runs")
        ok = False
    return ok


def test_read_only_by_default():
    """Default mode writes no file into the inbox."""
    tmp = tempfile.mkdtemp(prefix="afc-handoff-ro-")
    inbox = os.path.join(tmp, "inbox")
    shutil.copytree(BASIC, inbox)
    try:
        before = set(os.listdir(inbox))
        ok, stdout, stderr = run(["--date", FIXED_DATE, inbox], expect_exit=0, label="read-only-default")
        after = set(os.listdir(inbox))
        if before != after:
            print(f"    FAIL: default run changed inbox contents: {after - before}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_write_mode():
    """--write saves NEW_THREAD_HANDOFF_<date>.md into the inbox."""
    tmp = tempfile.mkdtemp(prefix="afc-handoff-write-")
    inbox = os.path.join(tmp, "inbox")
    shutil.copytree(BASIC, inbox)
    try:
        ok, stdout, stderr = run(
            ["--write", "--date", FIXED_DATE, inbox],
            expect_exit=0,
            label="write-mode",
        )
        out_file = os.path.join(inbox, f"NEW_THREAD_HANDOFF_{FIXED_DATE}.md")
        if not os.path.isfile(out_file):
            print(f"    FAIL: expected handoff file at {out_file}")
            ok = False
        if "Wrote" not in stdout:
            print(f"    FAIL: expected 'Wrote' confirmation, got: {stdout[:200]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_blockers_reported():
    """A BLOCKED task is listed under Blockers."""
    tmp = tempfile.mkdtemp(prefix="afc-handoff-blocked-")
    inbox = os.path.join(tmp, "inbox")
    shutil.copytree(BASIC, inbox)
    try:
        # Flip alpha to BLOCKED and drop its report so it is a clean active task.
        os.remove(os.path.join(inbox, "report-alpha.md"))
        task_path = os.path.join(inbox, "task-Worker-alpha.md")
        with open(task_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("status: ASSIGNED", "status: BLOCKED")
        with open(task_path, "w", encoding="utf-8") as f:
            f.write(content)
        ok, stdout, stderr = run(["--date", FIXED_DATE, inbox], expect_exit=0, label="blockers")
        if "BLOCKED: alpha" not in stdout:
            print(f"    FAIL: expected 'BLOCKED: alpha' under Blockers, got: {stdout[:400]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_missing_inbox():
    """Missing INBOX_DIR -> exit 1."""
    ok, stdout, stderr = run(
        [os.path.join(BASE, "nonexistent-dir")],
        expect_exit=1,
        label="missing-inbox",
    )
    if "directory not found" not in stderr.lower():
        print(f"    WARNING: expected 'directory not found' in stderr, got: {stderr[:200]}")
    return ok


def test_orphan_report_fails():
    """An orphan report (no matching task) -> exit 1."""
    tmp = tempfile.mkdtemp(prefix="afc-handoff-orphan-")
    inbox = os.path.join(tmp, "inbox")
    shutil.copytree(BASIC, inbox)
    try:
        os.remove(os.path.join(inbox, "task-Worker-alpha.md"))
        ok, stdout, stderr = run(
            ["--date", FIXED_DATE, inbox],
            expect_exit=1,
            label="orphan-report-fails",
        )
        if "orphan" not in stderr.lower():
            print(f"    WARNING: expected 'orphan' in stderr, got: {stderr[:200]}")
        return ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_bad_date():
    """A malformed --date value -> exit 1."""
    ok, stdout, stderr = run(
        ["--date", "2026-13-99", BASIC],
        expect_exit=1,
        label="bad-date",
    )
    return ok


def main():
    print("Running afc-handoff.py fixture tests...")
    print()
    all_ok = True

    tests = [
        test_help,
        test_basic_sections,
        test_roster_rows_included,
        test_recent_events_summarized,
        test_next_action_review,
        test_deterministic,
        test_read_only_by_default,
        test_write_mode,
        test_blockers_reported,
        test_missing_inbox,
        test_orphan_report_fails,
        test_bad_date,
    ]

    for test_fn in tests:
        try:
            ok = test_fn()
        except Exception as exc:
            print(f"  [FAIL] {test_fn.__name__}: {exc}")
            ok = False
        if not ok:
            all_ok = False
        print()

    if all_ok:
        print("All fixture tests passed.")
        return 0
    print("Some fixture tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
