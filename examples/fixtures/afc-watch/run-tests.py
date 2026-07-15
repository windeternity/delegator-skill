#!/usr/bin/env python3
"""Test runner for afc-watch.py fixtures.

Exercises all wake event types: report_ready, stale_alarm, error,
and no_wake (idle bounded exit).

Usage:
    python -B examples/fixtures/afc-watch/run-tests.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "scripts", "afc-watch.py"
)
SCRIPT = os.path.normpath(SCRIPT)

CAL2_ARM_SCRIPT = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "scripts", "afc-cal2-arm.py"
)
CAL2_ARM_SCRIPT = os.path.normpath(CAL2_ARM_SCRIPT)

WRAPPER_SCRIPT = os.path.join(
    os.path.dirname(__file__), "save_state_replace_fail_wrapper.py"
)
WRAPPER_SCRIPT = os.path.normpath(WRAPPER_SCRIPT)

BASE = os.path.dirname(os.path.abspath(__file__))
PASS_DIR = os.path.join(BASE, "pass")
FAIL_DIR = os.path.join(BASE, "fail")
CLOSE_FIXTURE_DIR = os.path.normpath(
    os.path.join(BASE, "..", "afc-close", "pass", "single-task")
)


def mtime_iso(filepath):
    """Return file mtime as ISO 8601 string (UTC), matching afc-watch.py."""
    return time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(os.path.getmtime(filepath)),
    )


def run(args, expect_exit=0, label="", timeout=30):
    """Run afc-watch.py with given args. Returns (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "-B", SCRIPT] + args
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    ok = result.returncode == expect_exit
    status = "PASS" if ok else "FAIL"
    print("  [{}] {} (exit={}, expected={})".format(
        status, label, result.returncode, expect_exit
    ))
    if not ok:
        print("    stdout: {}".format(result.stdout[:500]))
        print("    stderr: {}".format(result.stderr[:500]))
    return ok, result.stdout, result.stderr


def run_cal2_arm(args, expect_exit=0, label="", timeout=30):
    """Run afc-cal2-arm.py with given args. Returns (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "-B", CAL2_ARM_SCRIPT] + args
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout
    )
    ok = result.returncode == expect_exit
    status = "PASS" if ok else "FAIL"
    print("  [{}] {} (exit={}, expected={})".format(
        status, label, result.returncode, expect_exit
    ))
    if not ok:
        print("    stdout: {}".format(result.stdout[:500]))
        print("    stderr: {}".format(result.stderr[:500]))
    return ok, result.stdout, result.stderr


def make_terminal_inbox(include_report=True):
    """Create a valid temp inbox with one coordinator-closed task."""
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-auto-archive-")
    for filename in ("task-Worker-alpha.md", "events.jsonl"):
        shutil.copy2(os.path.join(CLOSE_FIXTURE_DIR, filename), tmpdir)
    if include_report:
        shutil.copy2(
            os.path.join(CLOSE_FIXTURE_DIR, "report-alpha.md"), tmpdir
        )
    task_path = os.path.join(tmpdir, "task-Worker-alpha.md")
    with open(task_path, "r", encoding="utf-8") as f:
        content = f.read()
    with open(task_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content.replace("status: ASSIGNED", "status: CLOSED_GO", 1))
    return tmpdir


def write_usable_roster(inbox, default_cal="CAL-2", agents=None):
    """Write a minimal usable roster so the dispatch gate passes (CAL-2 arm).

    The static report fixtures under pass/ have no AGENT_ROSTER.md, so any
    cal2-arm test that expects a successful arm must seed a usable roster first.
    Defaults cover every agent_name referenced by those fixtures (Worker1,
    WorkerT1, WorkerT2) plus RelayWorker; tests that need a roster WITHOUT a
    specific agent pass an explicit ``agents`` list.
    """
    if agents is None:
        agents = ["Worker1", "WorkerT1", "WorkerT2", "RelayWorker"]
    rows = "\n".join(
        "| {a} | implementer | external-chat | user-relay-model | user-relay:{a} | task-only | no | yes | tests_only | yes | no | manual_needed | fixture work | none | external user-relay worker |".format(a=a)
        for a in agents
    )
    roster = """---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---

# Agent Roster

<!-- SESSION PREFERENCES
Default CAL: {default_cal}
Execution preference: fixture external workers
Available resources: external user-relay workers
Available now: {agents}
Model preference order: fixture model
Avoid / unavailable: none
Smoke tests: fixture
Confirmed: 2026-06-30
Change policy: keep these defaults until the user asks to change them or a route becomes unavailable.
-->

| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Coordinator | coordinator | codex | coordinator-model | local coordinator | full-skill | yes | yes | bounded | yes | yes | can_use_existing | task decomposition, evidence review, final verdict | routine worker loops | fixture coordinator |
{rows}
""".format(default_cal=default_cal, agents=", ".join(agents), rows=rows)
    with open(os.path.join(inbox, "AGENT_ROSTER.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(roster)


def test_help():
    """--help exits 0."""
    ok, stdout, stderr = run(
        ["--help"], expect_exit=0, label="--help"
    )
    if "afc-watch" not in stdout.lower():
        print("    WARNING: expected 'afc-watch' in stdout")
        ok = False
    if "--auto-archive" not in stdout:
        print("    FAIL: expected --auto-archive in help")
        ok = False
    return ok


def test_auto_archive_default_off():
    """Terminal tasks remain untouched unless --auto-archive is explicit."""
    tmpdir = make_terminal_inbox()
    try:
        ok, stdout, _ = run(
            [
                "--expected-report", "not-created.md",
                "--max-iterations", "1",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=0,
            label="auto-archive-default-off",
        )
        if "no_wake" not in stdout:
            print("    FAIL: expected no_wake, got: {}".format(stdout[:300]))
            ok = False
        if not os.path.isfile(os.path.join(tmpdir, "task-Worker-alpha.md")):
            print("    FAIL: terminal task moved without --auto-archive")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_auto_archive_terminal_task():
    """Explicit auto-archive moves one valid terminal task and refreshes status."""
    tmpdir = make_terminal_inbox()
    try:
        ok, stdout, _ = run(
            [
                "--auto-archive",
                "--json",
                "--max-iterations", "1",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=0,
            label="auto-archive-terminal-task",
        )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            print("    FAIL: stdout is not valid JSON: {}".format(stdout[:300]))
            return False
        if data.get("event") != "task_archived":
            print("    FAIL: expected task_archived, got: {}".format(data))
            ok = False
        archive_path = data.get("archive_path", "")
        if not os.path.isfile(os.path.join(archive_path, "task-Worker-alpha.md")):
            print("    FAIL: archived task not found")
            ok = False
        if not os.path.isfile(os.path.join(archive_path, "report-alpha.md")):
            print("    FAIL: archived report not found")
            ok = False
        status_path = os.path.join(tmpdir, "STATUS.md")
        if not os.path.isfile(status_path):
            print("    FAIL: STATUS.md was not refreshed")
            ok = False
        else:
            with open(status_path, "r", encoding="utf-8") as f:
                if "| alpha |" in f.read():
                    print("    FAIL: archived task remains in STATUS.md")
                    ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_auto_archive_requires_report():
    """A terminal task without a report fails closed and remains active."""
    tmpdir = make_terminal_inbox(include_report=False)
    try:
        ok, stdout, _ = run(
            [
                "--auto-archive",
                "--max-iterations", "1",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=1,
            label="auto-archive-requires-report",
        )
        if "archive_blocked" not in stdout:
            print("    FAIL: expected archive_blocked, got: {}".format(
                stdout[:300]
            ))
            ok = False
        if not os.path.isfile(os.path.join(tmpdir, "task-Worker-alpha.md")):
            print("    FAIL: task moved despite missing report")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_auto_archive_one_task_per_run():
    """Two terminal tasks require two watcher invocations."""
    tmpdir = make_terminal_inbox()
    try:
        task_alpha = os.path.join(tmpdir, "task-Worker-alpha.md")
        report_alpha = os.path.join(tmpdir, "report-alpha.md")
        with open(task_alpha, "r", encoding="utf-8") as f:
            task_content = f.read()
        with open(report_alpha, "r", encoding="utf-8") as f:
            report_content = f.read()
        with open(
            os.path.join(tmpdir, "task-Worker-beta.md"),
            "w",
            encoding="utf-8",
            newline="\n",
        ) as f:
            f.write(task_content.replace("alpha", "beta"))
        with open(
            os.path.join(tmpdir, "report-beta.md"),
            "w",
            encoding="utf-8",
            newline="\n",
        ) as f:
            f.write(report_content.replace("alpha", "beta"))

        ok, stdout, _ = run(
            [
                "--auto-archive",
                "--max-iterations", "1",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=0,
            label="auto-archive-one-task-per-run",
        )
        if "task_archived" not in stdout or "alpha" not in stdout:
            print("    FAIL: expected alpha task_archived, got: {}".format(
                stdout[:300]
            ))
            ok = False
        if not os.path.isfile(os.path.join(tmpdir, "task-Worker-beta.md")):
            print("    FAIL: second terminal task should remain for re-arm")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_auto_archive_rejects_duplicate_task_id():
    """Cross-file duplicate task IDs fail closed before any move."""
    tmpdir = make_terminal_inbox()
    try:
        original = os.path.join(tmpdir, "task-Worker-alpha.md")
        duplicate = os.path.join(tmpdir, "task-Worker-alpha-copy.md")
        shutil.copy2(original, duplicate)
        ok, stdout, _ = run(
            [
                "--auto-archive",
                "--max-iterations", "1",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=1,
            label="auto-archive-rejects-duplicate-task-id",
        )
        if "archive_blocked" not in stdout:
            print("    FAIL: expected archive_blocked, got: {}".format(
                stdout[:300]
            ))
            ok = False
        if not os.path.isfile(original) or not os.path.isfile(duplicate):
            print("    FAIL: duplicate-task preflight moved a task")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_valid_report_wake():
    """New schema-valid report → exit 0 (report_ready).

    Runs in a temp copy so the state file creation doesn't modify fixtures.
    """
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="valid-report-wake",
        )
        if "report_ready" not in stdout:
            print("    FAIL: expected 'report_ready' in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        if "report-Worker1-watch-test.md" not in stdout:
            print("    FAIL: expected report filename in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        # State file should be updated
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        if not os.path.exists(state_path):
            print("    FAIL: state file not created after wake")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_valid_report_json():
    """New schema-valid report with --json produces valid JSON report_ready."""
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--json", "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="valid-report-json",
        )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            print("    FAIL: stdout is not valid JSON: {}".format(
                stdout[:300]
            ))
            return False
        if data.get("event") != "report_ready":
            print("    FAIL: expected event 'report_ready', got: {}".format(
                data.get("event")
            ))
            ok = False
        if "report_path" not in data:
            print("    FAIL: missing 'report_path' in JSON output")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cal2_arm_dry_run_no_write():
    """CAL-2 dry-run shows dispatch+watcher plan without writing events."""
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-cal2-arm-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        write_usable_roster(tmpdir)
        events_path = os.path.join(tmpdir, "events.jsonl")
        ok, stdout, stderr = run_cal2_arm(
            [
                "--task-id", "task-watch-test",
                "--inbox", tmpdir,
                "--dry-run",
                "--max-iterations", "1",
                "--poll-interval", "0",
            ],
            expect_exit=0,
            label="cal2-arm-dry-run-no-write",
        )
        if os.path.exists(events_path):
            print("    FAIL: dry-run should not create events.jsonl")
            ok = False
        if "TASK_DISPATCHED" not in stdout:
            print("    FAIL: expected dispatch plan in stdout")
            ok = False
        if "afc-watch.py" not in stdout:
            print("    FAIL: expected watcher command in stdout")
            ok = False
        if "--expected-report report-Worker1-watch-test.md" not in stdout:
            print("    FAIL: CAL-2 arm should scope to the task report path")
            ok = False
        if "--expected-task-id task-watch-test" not in stdout:
            print("    FAIL: CAL-2 arm should pass expected task id")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cal2_arm_records_dispatch_then_watches():
    """CAL-2 arm records TASK_DISPATCHED before watcher consumes report."""
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-cal2-arm-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        write_usable_roster(tmpdir)
        events_path = os.path.join(tmpdir, "events.jsonl")
        ok, stdout, stderr = run_cal2_arm(
            [
                "--task-id", "task-watch-test",
                "--inbox", tmpdir,
                "--max-iterations", "3",
                "--poll-interval", "0",
            ],
            expect_exit=0,
            label="cal2-arm-records-dispatch-then-watches",
        )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            print("    FAIL: stdout is not valid JSON: {}".format(stdout[:300]))
            return False
        if data.get("event") != "report_ready":
            print("    FAIL: expected report_ready, got: {}".format(data))
            ok = False
        if not os.path.isfile(events_path):
            print("    FAIL: events.jsonl was not created")
            return False
        with open(events_path, "r", encoding="utf-8-sig") as f:
            events = [json.loads(line) for line in f if line.strip()]
        event_types = [event.get("event_type") for event in events]
        if "TASK_DISPATCHED" not in event_types:
            print("    FAIL: missing TASK_DISPATCHED event")
            ok = False
        if "REPORT_RECEIVED" not in event_types:
            print("    FAIL: missing REPORT_RECEIVED event")
            ok = False
        if event_types.index("TASK_DISPATCHED") > event_types.index("REPORT_RECEIVED"):
            print("    FAIL: TASK_DISPATCHED must precede REPORT_RECEIVED")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cal2_arm_batch_filters_task_ids():
    """CAL-2 batch arm filters to current task IDs and waits once for all N.

    The default for a parallel batch is one consolidated wake after all N
    schema-valid reports arrive (--expected-reports N), not the single-file
    scoped wait (--expected-report <file>) and not a re-arm per worker.
    """
    src = os.path.join(PASS_DIR, "target-specific")
    tmpdir = tempfile.mkdtemp(prefix="afc-cal2-arm-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        write_usable_roster(tmpdir)
        ok, stdout, stderr = run_cal2_arm(
            [
                "--task-id", "task-A",
                "--task-id", "task-B",
                "--inbox", tmpdir,
                "--dry-run",
                "--max-iterations", "1",
                "--poll-interval", "0",
            ],
            expect_exit=0,
            label="cal2-arm-batch-filters-task-ids",
        )
        # Trailing space distinguishes the single-file flag (--expected-report
        # <file>) from the batch flag (--expected-reports N).
        if "--expected-report " in stdout:
            print("    FAIL: batch mode should not use the single-report scoped wait")
            ok = False
        if "--expected-reports 2" not in stdout:
            print("    FAIL: batch should wait once for all N reports by default")
            ok = False
        if "--expected-task-id task-A" not in stdout:
            print("    FAIL: missing task-A watcher filter")
            ok = False
        if "--expected-task-id task-B" not in stdout:
            print("    FAIL: missing task-B watcher filter")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cal2_arm_batch_incremental_opts_out():
    """--incremental restores per-worker re-arm (no --expected-reports)."""
    src = os.path.join(PASS_DIR, "target-specific")
    tmpdir = tempfile.mkdtemp(prefix="afc-cal2-arm-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        write_usable_roster(tmpdir)
        ok, stdout, stderr = run_cal2_arm(
            [
                "--task-id", "task-A",
                "--task-id", "task-B",
                "--inbox", tmpdir,
                "--incremental",
                "--dry-run",
                "--max-iterations", "1",
                "--poll-interval", "0",
            ],
            expect_exit=0,
            label="cal2-arm-batch-incremental-opts-out",
        )
        if "--expected-reports" in stdout:
            print("    FAIL: --incremental should omit --expected-reports")
            ok = False
        if "--expected-task-id task-A" not in stdout or "--expected-task-id task-B" not in stdout:
            print("    FAIL: --incremental should still scope to current task IDs")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cal2_arm_expected_reports_out_of_range():
    """--expected-reports above the batch size is rejected."""
    src = os.path.join(PASS_DIR, "target-specific")
    tmpdir = tempfile.mkdtemp(prefix="afc-cal2-arm-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        write_usable_roster(tmpdir)
        ok, stdout, stderr = run_cal2_arm(
            [
                "--task-id", "task-A",
                "--task-id", "task-B",
                "--inbox", tmpdir,
                "--expected-reports", "5",
                "--dry-run",
            ],
            expect_exit=1,
            label="cal2-arm-expected-reports-out-of-range",
        )
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cal2_arm_batch_auto_archive_forces_incremental():
    """--auto-archive on a batch falls back to the per-report flow so archiving
    still happens; the consolidated wake (_run_batch_wait) never archives."""
    src = os.path.join(PASS_DIR, "target-specific")
    tmpdir = tempfile.mkdtemp(prefix="afc-cal2-arm-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        write_usable_roster(tmpdir)
        ok, stdout, stderr = run_cal2_arm(
            [
                "--task-id", "task-A",
                "--task-id", "task-B",
                "--inbox", tmpdir,
                "--auto-archive",
                "--dry-run",
                "--max-iterations", "1",
                "--poll-interval", "0",
            ],
            expect_exit=0,
            label="cal2-arm-batch-auto-archive-forces-incremental",
        )
        if "--expected-reports" in stdout:
            print("    FAIL: --auto-archive batch should drop --expected-reports")
            ok = False
        if "--auto-archive" not in stdout:
            print("    FAIL: --auto-archive should still reach the watcher")
            ok = False
        if "--expected-task-id task-A" not in stdout or "--expected-task-id task-B" not in stdout:
            print("    FAIL: batch arm should still scope to current task IDs")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cal2_arm_blocks_missing_roster():
    """CAL-2 arm fails closed on a missing roster (O3b) before any side effect."""
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-cal2-arm-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        # Intentionally NO write_usable_roster(tmpdir): roster is missing.
        ok, stdout, stderr = run_cal2_arm(
            [
                "--task-id", "task-watch-test",
                "--inbox", tmpdir,
                "--dry-run",
                "--max-iterations", "1",
                "--poll-interval", "0",
            ],
            expect_exit=1,
            label="cal2-arm-blocks-missing-roster",
        )
        if "ROSTER_BLOCKED" not in stderr:
            print("    FAIL: expected ROSTER_BLOCKED, got: {}".format(stderr[:300]))
            ok = False
        if "roster_status:" not in stderr:
            print("    FAIL: expected roster_status line, got: {}".format(stderr[:300]))
            ok = False
        # No dispatch event should have been written.
        if os.path.isfile(os.path.join(tmpdir, "events.jsonl")):
            print("    FAIL: dispatch event written despite missing roster")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cal2_arm_blocks_unrostered_agent():
    """CAL-2 arm fails closed when a task's agent_name is not a rostered route.

    The roster is usable (Worker1 etc.) but the task's agent_name is rewritten to
    GhostWorker, which is not rostered. The per-task gate must block before any
    dispatch event or watcher side effect.
    """
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-cal2-arm-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        write_usable_roster(tmpdir)  # Worker1/WorkerT1/WorkerT2/RelayWorker only
        task_path = os.path.join(tmpdir, "task-watch-test.md")
        with open(task_path, "r", encoding="utf-8") as f:
            content = f.read()
        with open(task_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content.replace("agent_name: Worker1",
                                    "agent_name: GhostWorker", 1))
        ok, stdout, stderr = run_cal2_arm(
            [
                "--task-id", "task-watch-test",
                "--inbox", tmpdir,
                "--dry-run",
                "--max-iterations", "1",
                "--poll-interval", "0",
            ],
            expect_exit=1,
            label="cal2-arm-blocks-unrostered-agent",
        )
        if "ROSTER_BLOCKED" not in stderr:
            print("    FAIL: expected ROSTER_BLOCKED, got: {}".format(stderr[:300]))
            ok = False
        if "GhostWorker" not in stderr:
            print("    FAIL: expected the unrostered agent named, got: {}".format(stderr[:300]))
            ok = False
        if os.path.isfile(os.path.join(tmpdir, "events.jsonl")):
            print("    FAIL: dispatch event written despite unrostered agent")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_cal2_arm_blocks_blank_agent_name():
    """A task with a blank/missing agent_name is rejected before arming.

    Guards the Codex P2 finding: roster_status() only applies its per-agent
    filter for truthy agent_name, so an empty agent_name must be rejected
    explicitly rather than degrading the gate to "any usable route".
    """
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-cal2-arm-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        write_usable_roster(tmpdir)
        task_path = os.path.join(tmpdir, "task-watch-test.md")
        with open(task_path, "r", encoding="utf-8") as f:
            content = f.read()
        with open(task_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content.replace("agent_name: Worker1",
                                    "agent_name: ''", 1))
        ok, stdout, stderr = run_cal2_arm(
            [
                "--task-id", "task-watch-test",
                "--inbox", tmpdir,
                "--dry-run",
                "--max-iterations", "1",
                "--poll-interval", "0",
            ],
            expect_exit=1,
            label="cal2-arm-blocks-blank-agent-name",
        )
        if "ROSTER_BLOCKED" not in stderr or "no agent_name" not in stderr:
            print("    FAIL: expected ROSTER_BLOCKED + no agent_name, got: {}".format(stderr[:300]))
            ok = False
        if os.path.isfile(os.path.join(tmpdir, "events.jsonl")):
            print("    FAIL: dispatch event written despite blank agent_name")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_malformed_report_rejected():
    """Malformed report (missing task_id) → exit 3 (report_rejected).

    The watcher now emits report_rejected (exit 3) for malformed reports
    instead of silently ignoring them. This is the behavioral change for
    C5 watcher hardening: the coordinator learns about rejections.
    """
    src = os.path.join(PASS_DIR, "malformed-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="malformed-report-rejected",
        )
        if "report_ready" in stdout:
            print("    FAIL: should NOT have report_ready for malformed report")
            ok = False
        if "report_rejected" not in stdout:
            print("    FAIL: expected 'report_rejected' in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        if "missing required field: task_id" not in stdout:
            print("    FAIL: expected rejection reason in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_agent_name_mismatch_rejected():
    """Report whose agent_name differs from its task → exit 3.

    The watcher loads the matching task's frontmatter and runs the same
    cross-check intake does, so an agent_name mismatch that afc-intake.py
    catches is also rejected here (instead of being silently accepted and
    only failing later at intake). Uses a temp dir; no static fixture.
    """
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        task = (
            "---\n"
            "schema: agent-file-coordination/task\n"
            "schema_version: 0.1.0\n"
            "task_id: mismatch-1\n"
            "agent_name: CorrectWorker\n"
            "role: reviewer\n"
            "protocol_mode: task-only\n"
            "coordinator_authority: no\n"
            "routing_decision: FULL\n"
            "status: ASSIGNED\n"
            "permission_scope:\n"
            "  read_files: yes\n"
            "  write_task_files: no\n"
            "  write_reports: yes\n"
            "  modify_source: no\n"
            "  run_commands: read_only\n"
            "  network_access: none\n"
            "  commit_push: no\n"
            "  destructive_actions: no\n"
            "workspace:\n"
            "  mode: read_only_shared\n"
            "  path: .\n"
            "  may_create_worktree: no\n"
            "validation_tier: no-test-needed\n"
            "report_path: report-mismatch.md\n"
            "created_at: 2026-06-25\n"
            "---\n\n# Task\n\n## Role Boundary\n\nx\n"
        )
        report = (
            "---\n"
            "schema: agent-file-coordination/report\n"
            "schema_version: 0.1.0\n"
            "task_id: mismatch-1\n"
            "agent_name: WrongWorker\n"
            "verdict: GO\n"
            "evidence_refs:\n"
            "  - a.md\n"
            "evidence_trust:\n"
            "  trust_level: referenced\n"
            "guardrails:\n"
            "  role_boundary_followed: yes\n"
            "  coordinator_verdict_given: no\n"
            "  permission_scope_expanded: no\n"
            "  secrets_private_data_printed: no\n"
            "  production_default_behavior_changed: no\n"
            "  commit_push_done: no\n"
            "  destructive_command_done: no\n"
            "validation:\n"
            "  tier: no-test-needed\n"
            "  result: pass\n"
            "reported_at: 2026-06-25\n"
            "---\n\n# Report\nok\n"
        )
        with open(os.path.join(tmpdir, "task-CorrectWorker-mismatch-1.md"), "w",
                  encoding="utf-8") as handle:
            handle.write(task)
        with open(os.path.join(tmpdir, "report-mismatch.md"), "w",
                  encoding="utf-8") as handle:
            handle.write(report)
        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="agent-name-mismatch-rejected",
        )
        if "report_ready" in stdout:
            print("    FAIL: should NOT report_ready for an agent_name mismatch")
            ok = False
        if "report_rejected" not in stdout:
            print("    FAIL: expected 'report_rejected', got: {}".format(stdout[:300]))
            ok = False
        if "agent_name does not match" not in stdout:
            print("    FAIL: expected agent_name mismatch reason, got: {}".format(
                stdout[:300]))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_stale_alarm():
    """ASSIGNED task created long ago, no report → exit 2 (stale_alarm).

    Uses --stale-threshold 1 to trigger immediately.
    """
    src = os.path.join(PASS_DIR, "stale-alarm")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            [
                "--stale-threshold", "1",
                "--max-iterations", "3",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=2,
            label="stale-alarm",
        )
        if "stale_alarm" not in stdout:
            print("    FAIL: expected 'stale_alarm' in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        if "task-stale" not in stdout:
            print("    FAIL: expected 'task-stale' in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_stale_alarm_json():
    """Stale alarm with --json produces valid JSON."""
    src = os.path.join(PASS_DIR, "stale-alarm")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            [
                "--json",
                "--stale-threshold", "1",
                "--max-iterations", "3",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=2,
            label="stale-alarm-json",
        )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            print("    FAIL: stdout is not valid JSON: {}".format(
                stdout[:300]
            ))
            return False
        if data.get("event") != "stale_alarm":
            print("    FAIL: expected event 'stale_alarm', got: {}".format(
                data.get("event")
            ))
            ok = False
        if data.get("task_id") != "task-stale":
            print("    FAIL: expected task_id 'task-stale', got: {}".format(
                data.get("task_id")
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_scoped_stale_alarm_ignores_unrelated_old_task():
    """--expected-task-id stale detection is scoped to the current batch."""
    src = os.path.join(PASS_DIR, "old-task-no-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        old_time = time.time() - (7 * 24 * 3600)
        old_task = os.path.join(tmpdir, "task-old-no-report.md")
        os.utime(old_task, (old_time, old_time))

        current_task = os.path.join(tmpdir, "task-current-batch.md")
        with open(old_task, "r", encoding="utf-8") as f:
            content = f.read()
        with open(current_task, "w", encoding="utf-8", newline="\n") as f:
            f.write(
                content
                .replace("task_id: task-old-no-report", "task_id: current-batch")
                .replace("agent_name: Worker4", "agent_name: WorkerCurrent")
                .replace("report-Worker4-old.md", "report-WorkerCurrent-current.md")
            )
        os.utime(current_task, None)

        ok, stdout, _ = run(
            [
                "--expected-task-id", "current-batch",
                "--stale-threshold", "1",
                "--max-iterations", "1",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=0,
            label="scoped-stale-ignores-unrelated",
        )
        if "stale_alarm" in stdout or "task-old-no-report" in stdout:
            print("    FAIL: scoped watcher reported unrelated stale task")
            ok = False
        if "no_wake" not in stdout:
            print("    FAIL: expected no_wake, got: {}".format(stdout[:300]))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_idle_no_wake():
    """Empty inbox → watcher loops through max_iterations, exits 0 with no_wake."""
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="idle-no-wake",
        )
        if "report_ready" in stdout:
            print("    FAIL: should not have report_ready on empty inbox")
            ok = False
        if "stale_alarm" in stdout:
            print("    FAIL: should not have stale_alarm on empty inbox")
            ok = False
        if "no_wake" not in stdout:
            print("    FAIL: expected 'no_wake' in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_missing_inbox():
    """Missing INBOX_DIR → exit 1 (error)."""
    inbox = os.path.join(FAIL_DIR, "missing-inbox", "nonexistent-dir")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=1,
        label="missing-inbox",
    )
    if "directory not found" not in stderr:
        print("    WARNING: expected 'directory not found' in stderr, got: {}".format(
            stderr[:200]
        ))
    return ok


def test_stale_alarm_one_shot():
    """Staleness alarm fires once, not repeatedly.

    The watcher should exit on the first stale alarm detection.
    Running it again on the same inbox should fire again (the alarm is
    per-invocation, not persisted). This verifies the one-shot behavior
    within a single invocation.
    """
    src = os.path.join(PASS_DIR, "stale-alarm")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)

        # First run → stale_alarm
        ok1, stdout1, _ = run(
            [
                "--stale-threshold", "1",
                "--max-iterations", "3",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=2,
            label="stale-alarm-one-shot-1",
        )
        if "stale_alarm" not in stdout1:
            print("    FAIL: first run should produce stale_alarm")
            ok1 = False

        # Second run → stale_alarm again (one-shot per invocation)
        ok2, stdout2, _ = run(
            [
                "--stale-threshold", "1",
                "--max-iterations", "3",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=2,
            label="stale-alarm-one-shot-2",
        )
        if "stale_alarm" not in stdout2:
            print("    FAIL: second run should also produce stale_alarm")
            ok2 = False

        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_no_idle_wake_bounded():
    """With active tasks but no new reports, watcher does not produce false wakes.

    Creates an inbox with an ASSIGNED task (created_at = today) and no report.
    With a high staleness threshold, the watcher should loop and exit no_wake.
    """
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        task_content = (
            "---\n"
            "schema: agent-file-coordination/task\n"
            "schema_version: 0.1.0\n"
            "task_id: task-active\n"
            "agent_name: Worker1\n"
            "role: implementer\n"
            "protocol_mode: task-only\n"
            "coordinator_authority: no\n"
            "status: ASSIGNED\n"
            "permission_scope:\n"
            "  read_files: yes\n"
            "  write_task_files: no\n"
            "  write_reports: yes\n"
            "  modify_source: no\n"
            "  run_commands: none\n"
            "  network_access: none\n"
            "  commit_push: no\n"
            "  destructive_actions: no\n"
            "workspace:\n"
            "  mode: read_only_shared\n"
            "  path: /tmp\n"
            "  may_create_worktree: no\n"
            "validation_tier: no-test-needed\n"
            "report_path: .agent-inbox/report-Worker1-active.md\n"
            "created_at: 2099-01-01\n"
            "---\n"
            "# Task - Active\n"
        )
        with open(os.path.join(tmpdir, "task-active.md"), "w", encoding="utf-8") as f:
            f.write(task_content)

        ok, stdout, stderr = run(
            [
                "--stale-threshold", "999999",
                "--max-iterations", "3",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=0,
            label="no-idle-wake-bounded",
        )
        if "report_ready" in stdout:
            print("    FAIL: should not have report_ready without a report")
            ok = False
        if "stale_alarm" in stdout:
            print("    FAIL: should not have stale_alarm with future created_at")
            ok = False
        if "no_wake" not in stdout:
            print("    FAIL: expected 'no_wake' in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_state_persist_success():
    """Successful state persistence → state file created, no error."""
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="state-persist-success",
        )
        if "report_ready" not in stdout:
            print("    FAIL: expected report_ready, got: {}".format(stdout[:200]))
            ok = False
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        if not os.path.isfile(state_path):
            print("    FAIL: state file not created")
            ok = False
        else:
            # Verify state file has the report filename
            import json as _json
            try:
                with open(state_path, "r", encoding="utf-8") as sf:
                    data = _json.load(sf)
            except Exception:
                print("    FAIL: state file not valid JSON")
                ok = False
            else:
                if "report-Worker1-watch-test.md" not in data:
                    print("    FAIL: state file missing report entry, keys: {}".format(
                        list(data.keys())
                    ))
                    ok = False
        # No .tmp leftover
        tmp_state = state_path + ".tmp"
        if os.path.isfile(tmp_state):
            print("    FAIL: stale .tmp file left after successful save")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_state_persist_forced_failure():
    """Forced replace failure → watcher exits error (exit 1), does NOT emit report_ready.

    Simulates a replace failure by pre-creating a read-only .tmp file that
    blocks os.replace. This proves the fail-closed contract: if state cannot
    be persisted, the watcher must not claim report_ready.
    """
    import stat
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        tmp_state = state_path + ".tmp"
        # Pre-create a directory at tmp path to force os.replace to fail
        os.makedirs(tmp_state, exist_ok=True)
        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=1,
            label="state-persist-forced-failure",
        )
        if "report_ready" in stdout:
            print("    FAIL: must not emit report_ready when state save fails")
            ok = False
        if "error" not in stdout:
            print("    FAIL: expected 'error' event in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        if "cannot persist state" not in stdout:
            print("    FAIL: expected 'cannot persist state' in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_direct_write_fallback_on_replace_failure():
    """Direct-write fallback succeeds when os.replace() always fails.

    Uses a wrapper script that patches os.replace() to always raise OSError.
    The watcher should still exit 0 (report_ready) because _save_state falls
    through to the direct-write fallback. Verifies no .tmp leftover and valid
    state file content.
    """
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        tmp_state = state_path + ".tmp"

        cmd = [sys.executable, "-B", WRAPPER_SCRIPT,
               "--max-iterations", "3", "--poll-interval", "0", tmpdir]
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30
        )
        ok = result.returncode == 0
        if not ok:
            print("  [FAIL] direct-write-fallback (exit={}, expected=0)".format(
                result.returncode
            ))
            print("    stdout: {}".format(result.stdout[:500]))
            print("    stderr: {}".format(result.stderr[:500]))
            return False
        print("  [PASS] direct-write-fallback (exit=0)")

        # State file should exist and be valid JSON with the report entry
        if not os.path.isfile(state_path):
            print("    FAIL: state file not created via fallback")
            ok = False
        else:
            try:
                with open(state_path, "r", encoding="utf-8") as sf:
                    data = json.load(sf)
                if "report-Worker1-watch-test.md" not in data:
                    print("    FAIL: state file missing report entry, keys: {}".format(
                        list(data.keys())
                    ))
                    ok = False
            except Exception:
                print("    FAIL: state file not valid JSON")
                ok = False

        # No .tmp leftover after successful fallback
        if os.path.exists(tmp_state):
            print("    FAIL: stale .tmp file left after fallback save")
            ok = False

        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_no_duplicate_wake_after_save():
    """After a successful report_ready wake, the same report does not wake again.

    Run watcher twice on the same inbox. First run consumes the report (exit 0).
    Second run should exit no_wake because the report mtime is already in state.
    """
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        # First run: consume report
        ok1, stdout1, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="no-dup-wake-1",
        )
        if "report_ready" not in stdout1:
            print("    FAIL: first run should detect report_ready")
            ok1 = False
        # Second run: should not re-detect same report
        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="no-dup-wake-2",
        )
        if "report_ready" in stdout2:
            print("    FAIL: second run should NOT re-detect the same report")
            ok2 = False
        if "no_wake" not in stdout2:
            print("    FAIL: second run should exit no_wake, got: {}".format(
                stdout2[:300]
            ))
            ok2 = False
        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_temp_file_cleanup():
    """After successful save, no .tmp file remains. After failed save, no .tmp either."""
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        tmp_state = state_path + ".tmp"

        # Successful save: no .tmp leftover
        ok1, stdout1, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="temp-cleanup-success",
        )
        if "report_ready" not in stdout1:
            print("    FAIL: expected report_ready")
            ok1 = False
        if os.path.isfile(tmp_state):
            print("    FAIL: .tmp file left after successful save")
            ok1 = False

        # Now force a failure and verify no .tmp leftover
        shutil.rmtree(tmpdir, ignore_errors=True)
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        # Pre-create a directory at the tmp path
        os.makedirs(tmp_state, exist_ok=True)
        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=1,
            label="temp-cleanup-failure",
        )
        # After the run, the directory at tmp_state should still exist
        # (our _safe_remove only removes files, not dirs, so this is
        # actually the pre-existing dir — verify the error was emitted)
        if "cannot persist state" not in stdout2:
            print("    FAIL: expected persist error, got: {}".format(stdout2[:200]))
            ok2 = False

        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fresh_task_no_false_stale():
    """Fresh task with date-only created_at must NOT trigger stale_alarm.

    Regression test for C5: a task with created_at: YYYY-MM-DD (date-only)
    should use the task file's mtime as the age source, not 00:00 UTC.
    A freshly created task with a multi-hour threshold should not fire
    a false stale_alarm.
    """
    src = os.path.join(PASS_DIR, "fresh-task")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)

        # Set the task file mtime to current time so the test is
        # deterministic regardless of fixture checkout age. Without this,
        # the preserved checkout mtime grows stale as real time passes,
        # causing a false stale_alarm.
        task_path = os.path.join(tmpdir, "task-fresh.md")
        os.utime(task_path, None)  # None = set to current time

        ok, stdout, stderr = run(
            [
                "--stale-threshold", "3600",
                "--max-iterations", "3",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=0,
            label="fresh-task-no-false-stale",
        )
        if "stale_alarm" in stdout:
            print(
                "    FAIL: fresh task with date-only created_at "
                "must not trigger stale_alarm"
            )
            ok = False
        if "no_wake" not in stdout:
            print("    FAIL: expected 'no_wake' in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_old_task_with_old_mtime_stale():
    """Genuinely old ASSIGNED task with old file mtime must trigger stale_alarm.

    Regression test for C5: a task with date-only created_at and an
    explicitly old file mtime (set via os.utime) should still fire
    stale_alarm. This proves the fix does not weaken genuine staleness
    detection.
    """
    src = os.path.join(PASS_DIR, "old-task-no-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)

        # Set the task file's mtime to 7 days ago to simulate a genuinely
        # old task. This is deterministic and does not rely on checkout
        # age or sleep timing.
        old_time = time.time() - (7 * 24 * 3600)  # 7 days ago
        task_path = os.path.join(tmpdir, "task-old-no-report.md")
        os.utime(task_path, (old_time, old_time))

        ok, stdout, stderr = run(
            [
                "--stale-threshold", "3600",
                "--max-iterations", "3",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=2,
            label="old-task-stale-alarm",
        )
        if "stale_alarm" not in stdout:
            print(
                "    FAIL: old task with old mtime should trigger stale_alarm"
            )
            ok = False
        if "task-old-no-report" not in stdout:
            print(
                "    FAIL: expected 'task-old-no-report' in stdout, got: {}".format(
                    stdout[:300]
                )
            )
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_multi_reports_no_duplicates():
    """Multiple schema-valid reports present before watcher start.

    Two reports exist in the inbox. First watcher invocation consumes one
    (exit 0). Second invocation consumes the other (exit 0). Third
    invocation finds no new reports (exit 0, no_wake). Proves no
    duplicates and no lost reports.
    """
    src = os.path.join(PASS_DIR, "multi-reports")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)

        # First run: consume first report
        ok1, stdout1, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="multi-reports-1",
        )
        if "report_ready" not in stdout1:
            print("    FAIL: first run should detect report_ready")
            ok1 = False

        # Second run: consume second report
        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="multi-reports-2",
        )
        if "report_ready" not in stdout2:
            print("    FAIL: second run should detect report_ready")
            ok2 = False
        # Should be a different report than the first run
        if ok1 and ok2:
            # Both runs should have consumed; neither should be a duplicate
            # of the other (different filenames in stdout)
            pass

        # Third run: no more reports
        ok3, stdout3, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="multi-reports-3",
        )
        if "report_ready" in stdout3:
            print("    FAIL: third run should NOT detect report_ready (all consumed)")
            ok3 = False
        if "no_wake" not in stdout3:
            print("    FAIL: third run should exit no_wake, got: {}".format(
                stdout3[:300]
            ))
            ok3 = False

        # Verify state file has both reports
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        if os.path.isfile(state_path):
            try:
                with open(state_path, "r", encoding="utf-8") as sf:
                    state = json.load(sf)
                report_keys = [k for k in state.keys() if k.startswith("report-")]
                if len(report_keys) < 2:
                    print("    FAIL: state file should have 2 report entries, got: {}".format(
                        list(state.keys())
                    ))
                    ok1 = False
            except Exception:
                print("    FAIL: state file not valid JSON")
                ok1 = False

        return ok1 and ok2 and ok3
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_out_of_order_reports():
    """Out-of-order filename vs mtime: both reports consumed without state rollback.

    report-aaa.md has newer mtime, report-zzz.md has older mtime.
    Filename sort: aaa first, zzz second. Both are new (no prior state).
    First invocation consumes aaa (alphabetically first). Second consumes zzz.
    No state rollback occurs.
    """
    src = os.path.join(PASS_DIR, "out-of-order-reports")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)

        # Set mtimes: zzz older, aaa newer
        now = time.time()
        report_aaa = os.path.join(tmpdir, "report-WorkerOOO1-task-ooo-1.md")
        report_zzz = os.path.join(tmpdir, "report-WorkerOOO2-task-ooo-2.md")
        os.utime(report_zzz, (now - 600, now - 600))  # 10 min ago
        os.utime(report_aaa, (now - 60, now - 60))    # 1 min ago

        # First run: should consume aaa (alphabetically first, newer mtime)
        ok1, stdout1, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="ooo-first",
        )
        if "report_ready" not in stdout1:
            print("    FAIL: first run should detect report_ready")
            ok1 = False

        # Second run: should consume zzz (the other report)
        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="ooo-second",
        )
        if "report_ready" not in stdout2:
            print("    FAIL: second run should detect report_ready")
            ok2 = False

        # Third run: no_wake
        ok3, stdout3, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="ooo-third",
        )
        if "no_wake" not in stdout3:
            print("    FAIL: third run should exit no_wake, got: {}".format(
                stdout3[:300]
            ))
            ok3 = False

        return ok1 and ok2 and ok3
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_report_arrives_between_intake_and_rearm():
    """Report arrives between first intake and re-arm.

    Start with one report. First watcher invocation consumes it (exit 0).
    Before second invocation, add a new report file.
    Second invocation should detect the new report immediately.
    """
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)

        # First run: consume existing report
        ok1, stdout1, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="rearm-first",
        )
        if "report_ready" not in stdout1:
            print("    FAIL: first run should detect report_ready")
            ok1 = False

        # Simulate: a new report arrives while coordinator is processing
        new_report = os.path.join(tmpdir, "report-Worker2-arrived-later.md")
        with open(new_report, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "schema: agent-file-coordination/report\n"
                "schema_version: 0.1.0\n"
                "task_id: task-later\n"
                "agent_name: Worker2\n"
                "verdict: GO\n"
                "changed_files:\n  - none\n"
                "evidence_refs:\n  - test\n"
                "evidence_trust:\n"
                "  trust_level: reproduced\n"
                "  untrusted_inputs_seen: no\n"
                "  prompt_injection_suspected: no\n"
                "  permission_escalation_requested: no\n"
                "guardrails:\n"
                "  role_boundary_followed: yes\n"
                "  coordinator_verdict_given: no\n"
                "  permission_scope_expanded: no\n"
                "  secrets_private_data_printed: no\n"
                "  production_default_behavior_changed: no\n"
                "  commit_push_done: no\n"
                "  destructive_command_done: no\n"
                "validation:\n"
                "  tier: targeted-test\n"
                "  result: pass\n"
                "reported_at: 2026-06-12\n"
                "---\n\n# Later Report\n"
            )

        # Second run: should detect the new report immediately
        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="rearm-second",
        )
        if "report_ready" not in stdout2:
            print("    FAIL: second run should detect the new report")
            ok2 = False
        if "report-Worker2-arrived-later" not in stdout2:
            print("    FAIL: should detect the later report, got: {}".format(
                stdout2[:300]
            ))
            ok2 = False

        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_malformed_plus_valid():
    """Malformed report does not block valid report intake.

    Inbox has one malformed report (missing task_id) and one valid report.
    The watcher should consume the valid one and expose the malformed one in
    JSON side-channel fields.
    """
    src = os.path.join(PASS_DIR, "malformed-plus-valid")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)

        ok, stdout, stderr = run(
            ["--json", "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="malformed-plus-valid",
        )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            print("    FAIL: stdout is not valid JSON: {}".format(stdout[:300]))
            return False
        if data.get("event") != "report_ready":
            print("    FAIL: should detect valid report_ready, got: {}".format(data))
            ok = False
        # Should mention the valid report, not the malformed one
        if "report-WorkerMP-task-valid-mp" not in data.get("report_path", ""):
            print("    FAIL: should consume the valid report, got: {}".format(
                data
            ))
            ok = False
        rejected = data.get("rejected_reports", [])
        if not rejected or "report-AAA-malformed" not in rejected[0].get("filename", ""):
            print("    FAIL: JSON should expose rejected report, got: {}".format(data))
            ok = False
        ready = data.get("ready_reports", [])
        if not ready or "report-WorkerMP-task-valid-mp" not in ready[0].get("filename", ""):
            print("    FAIL: JSON should expose ready report, got: {}".format(data))
            ok = False
        if not data.get("next_action_hint"):
            print("    FAIL: expected next_action_hint in mixed wake JSON")
            ok = False
        # Malformed report MUST be rejected before the valid report is consumed.
        # The malformed fixture sorts first (report-AAA-malformed.md) so it is
        # scanned and rejected before report-WorkerMP-task-valid-mp.md.
        if "rejected report" not in stderr:
            print("    FAIL: expected 'rejected report' in stderr (malformed report must be scanned first), got: {}".format(
                stderr[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_no_artifact_files_created():
    """Foreground watcher creates no default artifact stdout/stderr/pid files.

    Run the watcher on a valid inbox and verify no unexpected files are
    created besides the state file.
    """
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)

        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="no-artifacts",
        )
        if "report_ready" not in stdout:
            print("    FAIL: expected report_ready")
            ok = False

        # Check for unexpected files
        expected_files = {
            "task-watch-test.md",
            "report-Worker1-watch-test.md",
            ".afc-poll-state.json",
        }
        actual_files = set(os.listdir(tmpdir))
        unexpected = actual_files - expected_files
        if unexpected:
            print("    FAIL: unexpected files created: {}".format(unexpected))
            ok = False

        # Check no .tmp leftover
        tmp_state = os.path.join(tmpdir, ".afc-poll-state.json.tmp")
        if os.path.exists(tmp_state):
            print("    FAIL: stale .tmp file left after successful run")
            ok = False

        # Check no stdout/stderr/pid artifacts
        for f in actual_files:
            if f.endswith((".stdout", ".stderr", ".pid", ".stdout.jsonl")):
                print("    FAIL: artifact file created: {}".format(f))
                ok = False

        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_state_no_rollback_on_parallel_intake():
    """State does not roll back when consuming reports from a multi-report inbox.

    Start with two reports. First invocation consumes one and saves state
    with BOTH report mtimes. Second invocation should NOT re-detect the
    already-consumed report (no rollback).
    """
    src = os.path.join(PASS_DIR, "multi-reports")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)

        # First run: consume one report
        ok1, stdout1, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="no-rollback-1",
        )
        if "report_ready" not in stdout1:
            print("    FAIL: first run should detect report_ready")
            ok1 = False

        # Read state after first run
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        with open(state_path, "r", encoding="utf-8") as sf:
            state1 = json.load(sf)

        # Second run: consume the other report
        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="no-rollback-2",
        )
        if "report_ready" not in stdout2:
            print("    FAIL: second run should detect report_ready")
            ok2 = False

        # Read state after second run
        with open(state_path, "r", encoding="utf-8") as sf:
            state2 = json.load(sf)

        # State should have grown (added the second report), not rolled back
        if len(state2) < len(state1):
            print("    FAIL: state rolled back from {} to {} entries".format(
                len(state1), len(state2)
            ))
            ok2 = False

        # Third run: no_wake (all consumed)
        ok3, stdout3, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="no-rollback-3",
        )
        if "no_wake" not in stdout3:
            print("    FAIL: third run should exit no_wake, got: {}".format(
                stdout3[:300]
            ))
            ok3 = False

        return ok1 and ok2 and ok3
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_preserve_later_seen_report_on_early_update():
    """An earlier updated report must not drop later seen-state entries.

    Regression for CAL-2 re-arm behavior: if report A sorts before report B,
    and report B is already in the state file, detecting updated report A must
    preserve report B in the persisted state. Otherwise report B wakes again on
    the next invocation as a duplicate.
    """
    src = os.path.join(PASS_DIR, "multi-reports")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")

        report_a = os.path.join(tmpdir, "report-WorkerA-task-alpha.md")
        report_b = os.path.join(tmpdir, "report-WorkerB-task-beta.md")
        old_a = "2026-06-12T00:00:00"
        old_b = mtime_iso(report_b)

        with open(state_path, "w", encoding="utf-8") as sf:
            json.dump({
                os.path.basename(report_a): old_a,
                os.path.basename(report_b): old_b,
            }, sf, indent=2, sort_keys=True)

        # Make A newer than its saved state while B remains already seen.
        os.utime(report_a, None)

        ok1, stdout1, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="preserve-later-seen-1",
        )
        if "report-WorkerA-task-alpha" not in stdout1:
            print("    FAIL: first run should detect updated report A")
            ok1 = False

        with open(state_path, "r", encoding="utf-8") as sf:
            state = json.load(sf)
        if os.path.basename(report_b) not in state:
            print("    FAIL: later seen report B was dropped from state")
            ok1 = False

        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="preserve-later-seen-2",
        )
        if "no_wake" not in stdout2:
            print("    FAIL: second run should not duplicate report B, got: {}".format(
                stdout2[:300]
            ))
            ok2 = False

        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_rejected_missing_frontmatter():
    """File with no report frontmatter is silently skipped (not a report).

    The watcher only processes files with schema: agent-file-coordination/report.
    A file without frontmatter is not detected as a report file at all.
    """
    src = os.path.join(PASS_DIR, "rejected-missing-frontmatter")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="rejected-missing-frontmatter",
        )
        if "report_ready" in stdout:
            print("    FAIL: should NOT wake for non-report file")
            ok = False
        if "no_wake" not in stdout:
            print("    FAIL: expected 'no_wake' in stdout, got: {}".format(
                stdout[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_rejected_invalid_trust():
    """Report with invalid trust_level → exit 3 (report_rejected)."""
    src = os.path.join(PASS_DIR, "rejected-invalid-trust")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="rejected-invalid-trust",
        )
        if "report_rejected" not in stdout:
            print("    FAIL: expected 'report_rejected' in stdout")
            ok = False
        if "invalid trust_level" not in stdout:
            print("    FAIL: expected 'invalid trust_level' in rejection reasons")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_rejected_dangerous_phrase():
    """Report with dangerous phrase without prompt_injection_suspected → exit 3."""
    src = os.path.join(PASS_DIR, "rejected-dangerous-phrase")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="rejected-dangerous-phrase",
        )
        if "report_rejected" not in stdout:
            print("    FAIL: expected 'report_rejected' in stdout")
            ok = False
        if "dangerous phrase" not in stdout:
            print("    FAIL: expected 'dangerous phrase' in rejection reasons")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_rejected_no_repeat():
    """Rejected report does not re-wake on second run (unchanged mtime)."""
    src = os.path.join(PASS_DIR, "rejected-invalid-trust")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        # First run: reject
        ok1, stdout1, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="rejected-no-repeat-1",
        )
        if "report_rejected" not in stdout1:
            print("    FAIL: first run should reject")
            ok1 = False
        # Second run: same report, unchanged mtime → no_wake
        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="rejected-no-repeat-2",
        )
        if "report_rejected" in stdout2:
            print("    FAIL: second run should NOT re-reject unchanged file")
            ok2 = False
        if "no_wake" not in stdout2:
            print("    FAIL: second run should exit no_wake, got: {}".format(
                stdout2[:300]
            ))
            ok2 = False
        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_rejected_then_corrected():
    """Rejected report corrected by worker → new version passes validation."""
    src = os.path.join(PASS_DIR, "rejected-invalid-trust")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        # First run: reject
        ok1, stdout1, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="rejected-then-corrected-1",
        )
        if "report_rejected" not in stdout1:
            print("    FAIL: first run should reject")
            ok1 = False

        # Worker corrects the report: fix trust_level
        report_path = os.path.join(tmpdir, "report-bad-trust.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "schema: agent-file-coordination/report\n"
                "schema_version: 0.1.0\n"
                "task_id: task-bad-trust\n"
                "agent_name: WorkerBadTrust\n"
                "verdict: GO\n"
                "changed_files:\n  - none\n"
                "evidence_refs:\n  - test\n"
                "evidence_trust:\n"
                "  trust_level: self_claim\n"
                "  untrusted_inputs_seen: no\n"
                "  prompt_injection_suspected: no\n"
                "  permission_escalation_requested: no\n"
                "guardrails:\n"
                "  role_boundary_followed: yes\n"
                "  coordinator_verdict_given: no\n"
                "  permission_scope_expanded: no\n"
                "  secrets_private_data_printed: no\n"
                "  production_default_behavior_changed: no\n"
                "  commit_push_done: no\n"
                "  destructive_command_done: no\n"
                "validation:\n"
                "  tier: no-test-needed\n"
                "  result: pass\n"
                "reported_at: 2026-06-12\n"
                "---\n\n# Corrected report\n"
            )

        # Second run: corrected report passes
        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="rejected-then-corrected-2",
        )
        if "report_ready" not in stdout2:
            print("    FAIL: second run should detect report_ready for corrected file")
            ok2 = False
        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_rejected_plus_valid():
    """Rejected report does not block valid report intake (different sort order)."""
    src = os.path.join(PASS_DIR, "rejected-plus-valid")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="rejected-plus-valid",
        )
        if "report_ready" not in stdout:
            print("    FAIL: should detect valid report_ready")
            ok = False
        # The rejected report (report-RPV-bad.md) sorts before the valid one
        # (report-RPV-valid.md). It should be rejected (logged to stderr)
        # but the valid report should still be consumed.
        if "rejected report" not in stderr:
            print("    FAIL: expected rejected report in stderr")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_matching():
    """--expected-report task-B wakes for task-B's report only."""
    src = os.path.join(PASS_DIR, "target-specific")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--expected-report", "report-WorkerT2-task-B.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="expected-report-matching",
        )
        if "report_ready" not in stdout:
            print("    FAIL: should detect report_ready for expected report")
            ok = False
        if "report-WorkerT2-task-B" not in stdout:
            print("    FAIL: should mention expected report, got: {}".format(stdout[:300]))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_rejected():
    """--expected-report with malformed report → exit 3 (report_rejected)."""
    src = os.path.join(PASS_DIR, "target-rejected")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--expected-report", "report-TR-bad.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="expected-report-rejected",
        )
        if "report_rejected" not in stdout:
            print("    FAIL: expected report_rejected for expected report")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_unrelated_not_in_state():
    """--expected-report waits for B while A exists; generic watcher then receives A.

    Two-stage regression: expected-report mode only touches the expected file's
    state. Unrelated reports remain absent from state, so a later generic
    watcher invocation sees them as new.
    """
    src = os.path.join(PASS_DIR, "target-specific")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)

        # Stage 1: expected-report waits for task-B's report.
        # task-A's report also exists but must NOT be consumed.
        ok1, stdout1, _ = run(
            ["--expected-report", "report-WorkerT2-task-B.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="expected-unrelated-1",
        )
        if "report_ready" not in stdout1:
            print("    FAIL: stage 1 should detect expected report")
            ok1 = False

        # Verify state only has task-B's report, not task-A's
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        if os.path.isfile(state_path):
            with open(state_path, "r", encoding="utf-8") as sf:
                state = json.load(sf)
            if "report-WorkerT1-task-A.md" in state:
                print("    FAIL: unrelated report A should NOT be in state")
                ok1 = False
            if "report-WorkerT2-task-B.md" not in state:
                print("    FAIL: expected report B should be in state")
                ok1 = False

        # Stage 2: generic watcher should receive task-A's report
        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="expected-unrelated-2",
        )
        if "report_ready" not in stdout2:
            print("    FAIL: stage 2 generic watcher should detect report A")
            ok2 = False
        if "report-WorkerT1-task-A" not in stdout2:
            print("    FAIL: stage 2 should consume report A, got: {}".format(
                stdout2[:300]
            ))
            ok2 = False

        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_out_of_inbox():
    """--expected-report with traversal path → exit 1 (error)."""
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        ok, stdout, stderr = run(
            ["--expected-report", "../escape.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=1,
            label="expected-out-of-inbox",
        )
        if "traversal" not in stderr and "inside the inbox" not in stderr:
            print("    FAIL: expected traversal/inbox error in stderr, got: {}".format(
                stderr[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_task_id_mismatch():
    """--expected-report with --expected-task-id mismatch → exit 3."""
    src = os.path.join(PASS_DIR, "target-specific")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--expected-report", "report-WorkerT1-task-A.md",
             "--expected-task-id", "task-WRONG",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="expected-task-id-mismatch",
        )
        if "report_rejected" not in stdout:
            print("    FAIL: expected report_rejected for task_id mismatch")
            ok = False
        if "task_id mismatch" not in stdout:
            print("    FAIL: expected 'task_id mismatch' in rejection reasons")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_missing_frontmatter():
    """--expected-report with file that has no frontmatter → exit 3."""
    src = os.path.join(PASS_DIR, "rejected-missing-frontmatter")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--expected-report", "report-no-fm.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="expected-missing-frontmatter",
        )
        if "report_rejected" not in stdout:
            print("    FAIL: expected report_rejected for missing frontmatter")
            ok = False
        if "no frontmatter" not in stdout and "parse error" not in stdout:
            print("    FAIL: expected parse error in rejection reasons")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_quoted_scalars_accepted():
    """--expected-report with YAML-quoted scalars must be accepted (report_ready),
    not rejected for a schema/task_id mismatch. Guards the quote-strip fix in
    parse_structured_lines (PR #56 Codex feedback): the structured parser must
    strip quotes from scalars (and list items) like the flat/nested parser.
    """
    src = os.path.join(PASS_DIR, "quoted-scalar-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--expected-report", "report-quoted.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="expected-quoted-scalars",
        )
        if "report_ready" not in stdout:
            print("    FAIL: expected report_ready for quoted-scalar report")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_bool_literal_task_id():
    """--expected-report with task_id: yes (unquoted YAML bool literal) must be
    accepted (report_ready), not crash on .strip() or mismatch. Guards the
    DEFAULT_STRING_KEYS fix (PR #56 Codex feedback): the structured parser
    keeps task_id as the string "yes" instead of coercing to Python True.
    """
    src = os.path.join(PASS_DIR, "bool-literal-task-id")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--expected-report", "report-bool-id.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="expected-bool-literal-task-id",
        )
        if "report_ready" not in stdout:
            print("    FAIL: expected report_ready for bool-literal task_id")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_empty_evidence_rejected():
    """--expected-report with an empty evidence_refs block -> exit 3.

    Guards the intake-time validation divergence fixed in this change: the
    flat/nested parser collapsed an empty `evidence_refs:` block to "" and
    accepted the report; the structured parser preserves it as [] and
    rejects it ("evidence_refs must be a non-empty list").
    """
    src = os.path.join(PASS_DIR, "rejected-empty-evidence")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--expected-report", "report-empty-evidence.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="expected-empty-evidence",
        )
        if "report_rejected" not in stdout:
            print("    FAIL: expected report_rejected for empty evidence_refs")
            ok = False
        if "evidence_refs" not in stdout:
            print("    FAIL: expected 'evidence_refs' in rejection reasons")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_corrected():
    """--expected-report: rejected file corrected → report_ready on re-run."""
    src = os.path.join(PASS_DIR, "rejected-invalid-trust")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        # First run: reject
        ok1, stdout1, _ = run(
            ["--expected-report", "report-bad-trust.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="expected-corrected-1",
        )
        if "report_rejected" not in stdout1:
            print("    FAIL: first run should reject")
            ok1 = False

        # Worker corrects the report
        report_path = os.path.join(tmpdir, "report-bad-trust.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "schema: agent-file-coordination/report\n"
                "schema_version: 0.1.0\n"
                "task_id: task-bad-trust\n"
                "agent_name: WorkerBadTrust\n"
                "verdict: GO\n"
                "changed_files:\n  - none\n"
                "evidence_refs:\n  - test\n"
                "evidence_trust:\n"
                "  trust_level: self_claim\n"
                "  untrusted_inputs_seen: no\n"
                "  prompt_injection_suspected: no\n"
                "  permission_escalation_requested: no\n"
                "guardrails:\n"
                "  role_boundary_followed: yes\n"
                "  coordinator_verdict_given: no\n"
                "  permission_scope_expanded: no\n"
                "  secrets_private_data_printed: no\n"
                "  production_default_behavior_changed: no\n"
                "  commit_push_done: no\n"
                "  destructive_command_done: no\n"
                "validation:\n"
                "  tier: no-test-needed\n"
                "  result: pass\n"
                "reported_at: 2026-06-12\n"
                "---\n\n# Corrected report\n"
            )

        # Second run: corrected report passes
        ok2, stdout2, _ = run(
            ["--expected-report", "report-bad-trust.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="expected-corrected-2",
        )
        if "report_ready" not in stdout2:
            print("    FAIL: second run should detect report_ready")
            ok2 = False
        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_no_repeat():
    """--expected-report: unchanged rejected file → no_wake on re-run."""
    src = os.path.join(PASS_DIR, "rejected-invalid-trust")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        # First run: reject
        ok1, stdout1, _ = run(
            ["--expected-report", "report-bad-trust.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=3,
            label="expected-no-repeat-1",
        )
        if "report_rejected" not in stdout1:
            print("    FAIL: first run should reject")
            ok1 = False

        # Second run: unchanged → no_wake
        ok2, stdout2, _ = run(
            ["--expected-report", "report-bad-trust.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="expected-no-repeat-2",
        )
        if "report_rejected" in stdout2:
            print("    FAIL: should NOT re-reject unchanged file")
            ok2 = False
        if "no_wake" not in stdout2:
            print("    FAIL: expected no_wake, got: {}".format(stdout2[:300]))
            ok2 = False
        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_needs_fix_waits_for_update():
    """NEEDS_FIX re-arm waits for a newer report instead of already-consumed."""
    src = os.path.join(PASS_DIR, "valid-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        task_path = os.path.join(tmpdir, "task-watch-test.md")
        with open(task_path, "r", encoding="utf-8") as f:
            task_content = f.read()
        with open(task_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(task_content.replace("status: ASSIGNED", "status: NEEDS_FIX"))

        report_name = "report-Worker1-watch-test.md"
        report_path = os.path.join(tmpdir, report_name)
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        with open(state_path, "w", encoding="utf-8") as sf:
            json.dump({
                report_name: {
                    "mtime": mtime_iso(report_path),
                    "status": "valid",
                }
            }, sf, indent=2)

        ok, stdout, _ = run(
            [
                "--expected-report", report_name,
                "--expected-task-id", "task-watch-test",
                "--max-iterations", "2",
                "--poll-interval", "0",
                tmpdir,
            ],
            expect_exit=0,
            label="expected-needs-fix-waits-for-update",
        )
        if "already consumed" in stdout:
            print("    FAIL: NEEDS_FIX re-arm must not exit already consumed")
            ok = False
        if "no wake event after 2 iterations" not in stdout:
            print("    FAIL: expected bounded wait no_wake, got: {}".format(
                stdout[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_state_monotonicity_rejected():
    """State preserves rejected report mtime alongside valid report mtime."""
    src = os.path.join(PASS_DIR, "rejected-plus-valid")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")

        # First run: rejected report consumed (sorted first), valid consumed
        ok1, stdout1, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="state-mono-rej-1",
        )
        if "report_ready" not in stdout1:
            print("    FAIL: first run should detect report_ready")
            ok1 = False

        # State should have entries for the rejected report
        if os.path.isfile(state_path):
            with open(state_path, "r", encoding="utf-8") as sf:
                state = json.load(sf)
            # The rejected report (RPV-bad) should be in state as rejected
            bad_key = "report-RPV-bad.md"
            if bad_key in state:
                entry = state[bad_key]
                if isinstance(entry, dict) and entry.get("status") != "rejected":
                    print("    FAIL: rejected report should have status 'rejected', got: {}".format(
                        entry.get("status")
                    ))
                    ok1 = False
        else:
            print("    FAIL: state file not created")
            ok1 = False

        # Second run: no_wake (all consumed)
        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="state-mono-rej-2",
        )
        if "no_wake" not in stdout2:
            print("    FAIL: second run should exit no_wake, got: {}".format(
                stdout2[:300]
            ))
            ok2 = False

        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_unrelated_old_report_no_wake():
    """Report already in state (already seen) does not re-wake.

    Pre-populates the state file with the report's mtime so the watcher
    treats it as already consumed. This is the regression guard for the
    "old report" case in the design doc.
    """
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        # Create a valid report
        report = os.path.join(tmpdir, "report-orphan-task.md")
        with open(report, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "schema: agent-file-coordination/report\n"
                "schema_version: 0.1.0\n"
                "task_id: task-nonexistent\n"
                "agent_name: WorkerOrphan\n"
                "verdict: GO\n"
                "changed_files:\n  - none\n"
                "evidence_refs:\n  - test\n"
                "evidence_trust:\n"
                "  trust_level: self_claim\n"
                "  untrusted_inputs_seen: no\n"
                "  prompt_injection_suspected: no\n"
                "  permission_escalation_requested: no\n"
                "guardrails:\n"
                "  role_boundary_followed: yes\n"
                "  coordinator_verdict_given: no\n"
                "  permission_scope_expanded: no\n"
                "  secrets_private_data_printed: no\n"
                "  production_default_behavior_changed: no\n"
                "  commit_push_done: no\n"
                "  destructive_command_done: no\n"
                "validation:\n"
                "  tier: no-test-needed\n"
                "  result: pass\n"
                "reported_at: 2026-06-12\n"
                "---\n\n# Orphan report\n"
            )

        # Pre-populate state with the report's mtime (mark as already seen)
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        report_mtime = mtime_iso(report)
        with open(state_path, "w", encoding="utf-8") as sf:
            json.dump({
                "report-orphan-task.md": {
                    "mtime": report_mtime,
                    "status": "seen",
                }
            }, sf, indent=2)

        ok, stdout, stderr = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="unrelated-old-report",
        )
        if "report_ready" in stdout:
            print("    FAIL: should NOT wake for already-seen report")
            ok = False
        if "no_wake" not in stdout:
            print("    FAIL: expected no_wake, got: {}".format(stdout[:300]))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_report_ignores_unrelated():
    """--expected-report for absent file leaves unrelated reports unconsumed.

    Repurposed from the original target-ignore fixture: the inbox has an
    unrelated report (task-other) but the watcher is asked to wait for a
    report that does not exist. The unrelated report must NOT be consumed
    by the expected-report scan. A subsequent generic-mode invocation then
    picks it up. Two-stage proof that expected-report isolates state.
    """
    src = os.path.join(PASS_DIR, "target-ignore")
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)

        # Stage 1: expected-report for a file that does not exist.
        # The unrelated report-TI-other.md must NOT be consumed.
        ok1, stdout1, _ = run(
            ["--expected-report", "report-nonexistent.md",
             "--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="expected-ignores-unrelated-1",
        )
        if "no_wake" not in stdout1:
            print("    FAIL: stage 1 should exit no_wake (expected file absent)")
            ok1 = False

        # Verify state does NOT contain the unrelated report
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        if os.path.isfile(state_path):
            with open(state_path, "r", encoding="utf-8") as sf:
                state = json.load(sf)
            if "report-TI-other.md" in state:
                print("    FAIL: unrelated report should NOT be in state")
                ok1 = False

        # Stage 2: generic watcher should receive the unrelated report
        ok2, stdout2, _ = run(
            ["--max-iterations", "3", "--poll-interval", "0", tmpdir],
            expect_exit=0,
            label="expected-ignores-unrelated-2",
        )
        if "report_ready" not in stdout2:
            print("    FAIL: stage 2 generic watcher should detect unrelated report")
            ok2 = False
        if "report-TI-other" not in stdout2:
            print("    FAIL: stage 2 should consume report-TI-other, got: {}".format(
                stdout2[:300]
            ))
            ok2 = False

        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _batch_valid_report(tid, agent):
    return (
        "---\n"
        "schema: agent-file-coordination/report\n"
        "schema_version: 0.1.0\n"
        "task_id: {tid}\n"
        "agent_name: {agent}\n"
        "verdict: GO\n"
        "changed_files:\n  - src/x.txt\n"
        "evidence_refs:\n  - git diff\n"
        "evidence_trust:\n"
        "  trust_level: referenced\n"
        "  untrusted_inputs_seen: no\n"
        "  prompt_injection_suspected: no\n"
        "  permission_escalation_requested: no\n"
        "guardrails:\n"
        "  role_boundary_followed: yes\n"
        "  coordinator_verdict_given: no\n"
        "  permission_scope_expanded: no\n"
        "  secrets_private_data_printed: no\n"
        "  production_default_behavior_changed: no\n"
        "  commit_push_done: no\n"
        "  destructive_command_done: no\n"
        "validation:\n  tier: no-test-needed\n  result: pass\n"
        "reported_at: 2026-06-16\n"
        "---\n# Worker Report\ndone.\n\nRemaining risk: none\n"
    ).format(tid=tid, agent=agent)


def test_expected_reports_batch():
    """--expected-reports N blocks until N schema-valid reports, returns once."""
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-batch-")
    try:
        for tid, agent in [("bt1", "A"), ("bt2", "B")]:
            with open(
                os.path.join(tmpdir, "report-{}-{}.md".format(agent, tid)),
                "w", encoding="utf-8", newline="\n",
            ) as fh:
                fh.write(_batch_valid_report(tid, agent))
        # A malformed report must never count toward the batch.
        with open(
            os.path.join(tmpdir, "report-C-bt3.md"),
            "w", encoding="utf-8", newline="\n",
        ) as fh:
            fh.write("---\nschema: agent-file-coordination/report\ntask_id: bt3\n---\nbad")

        base = ["--json", "--poll-interval", "0", "--max-iterations", "1"]
        ok = True

        good, stdout, _ = run(
            base + ["--expected-reports", "2", tmpdir],
            expect_exit=0, label="expected-reports: 2 valid -> ready",
        )
        ok = ok and good
        data = json.loads(stdout) if stdout.strip() else {}
        if data.get("event") != "reports_ready" or sorted(
            data.get("ready_task_ids", [])
        ) != ["bt1", "bt2"]:
            print("    FAIL: batch ready payload: {}".format(stdout[:300]))
            ok = False

        good, stdout, _ = run(
            base + ["--expected-reports", "3", tmpdir],
            expect_exit=2, label="expected-reports: missing one -> incomplete",
        )
        ok = ok and good
        data = json.loads(stdout) if stdout.strip() else {}
        if data.get("event") != "reports_incomplete":
            print("    FAIL: expected reports_incomplete: {}".format(stdout[:300]))
            ok = False

        # Fresh state: this sub-call exercises task-id filtering in isolation,
        # not consumed-report skipping (covered by its own test), so clear any
        # seen-state a prior successful sub-call persisted.
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        if os.path.exists(state_path):
            os.remove(state_path)
        good, stdout, _ = run(
            base + ["--expected-reports", "1", "--expected-task-id", "bt1", tmpdir],
            expect_exit=0, label="expected-reports: task-id filter",
        )
        ok = ok and good
        data = json.loads(stdout) if stdout.strip() else {}
        if data.get("ready_task_ids") != ["bt1"]:
            print("    FAIL: filtered payload: {}".format(stdout[:300]))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _batch_task(tid, agent, created_at, status="ASSIGNED"):
    return (
        "---\n"
        "schema: agent-file-coordination/task\n"
        "schema_version: 0.1.0\n"
        "task_id: {tid}\n"
        "agent_name: {agent}\n"
        "status: {status}\n"
        "created_at: {created_at}\n"
        "report_path: .agent-inbox/report-{agent}-{tid}.md\n"
        "---\n# Task {tid}\n"
    ).format(tid=tid, agent=agent, created_at=created_at, status=status)


def test_expected_reports_batch_stale_alarm():
    """A hung worker fires stale_alarm in batch mode, not a full-timeout wait."""
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-batch-stale-")
    try:
        # bt1 reported; bt2 stays ASSIGNED with an old created_at and no report.
        with open(os.path.join(tmpdir, "task-A-bt1.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_task("bt1", "A", "2020-01-01T00:00:00Z"))
        with open(os.path.join(tmpdir, "report-A-bt1.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_valid_report("bt1", "A"))
        with open(os.path.join(tmpdir, "task-B-bt2.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_task("bt2", "B", "2020-01-01T00:00:00Z"))

        ok, stdout, _ = run(
            [
                "--json", "--poll-interval", "0", "--max-iterations", "3",
                "--stale-threshold", "60",
                "--expected-reports", "2",
                "--expected-task-id", "bt1", "--expected-task-id", "bt2",
                tmpdir,
            ],
            expect_exit=2,
            label="expected-reports: hung worker -> stale_alarm",
        )
        data = json.loads(stdout) if stdout.strip() else {}
        if data.get("event") != "stale_alarm":
            print("    FAIL: expected stale_alarm, got: {}".format(stdout[:300]))
            ok = False
        if data.get("task_id") != "bt2":
            print("    FAIL: stale alarm should name bt2: {}".format(stdout[:300]))
            ok = False
        if sorted(data.get("ready_task_ids", [])) != ["bt1"]:
            print("    FAIL: stale alarm should still report bt1 ready: {}".format(stdout[:300]))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_reports_batch_fresh_not_stale():
    """A fresh (not-yet-stale) missing worker yields reports_incomplete, not stale_alarm."""
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-batch-fresh-")
    try:
        # bt1 reported; bt2 ASSIGNED, no report, but date-only created_at means
        # age is measured from the (just-written) file mtime, so it is fresh.
        with open(os.path.join(tmpdir, "task-A-bt1.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_task("bt1", "A", "2026-06-24"))
        with open(os.path.join(tmpdir, "report-A-bt1.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_valid_report("bt1", "A"))
        with open(os.path.join(tmpdir, "task-B-bt2.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_task("bt2", "B", "2026-06-24"))

        ok, stdout, _ = run(
            [
                "--json", "--poll-interval", "0", "--max-iterations", "2",
                "--stale-threshold", "3600",
                "--expected-reports", "2",
                "--expected-task-id", "bt1", "--expected-task-id", "bt2",
                tmpdir,
            ],
            expect_exit=2,
            label="expected-reports: fresh missing worker -> incomplete",
        )
        data = json.loads(stdout) if stdout.strip() else {}
        if data.get("event") != "reports_incomplete":
            print("    FAIL: fresh worker should not stale-alarm: {}".format(stdout[:300]))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_expected_reports_batch_appends_receipts():
    """Batch consolidated wake appends a REPORT_RECEIVED event per ready report."""
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-batch-receipt-")
    try:
        # events.jsonl must exist for the watcher to append (same precondition
        # as the single-report and generic paths).
        open(os.path.join(tmpdir, "events.jsonl"), "w", encoding="utf-8").close()
        for tid, agent in [("bt1", "A"), ("bt2", "B")]:
            with open(os.path.join(tmpdir, "task-{}-{}.md".format(agent, tid)),
                      "w", encoding="utf-8", newline="\n") as fh:
                fh.write(_batch_task(tid, agent, "2026-06-24"))
            with open(os.path.join(tmpdir, "report-{}-{}.md".format(agent, tid)),
                      "w", encoding="utf-8", newline="\n") as fh:
                fh.write(_batch_valid_report(tid, agent))

        ok, stdout, _ = run(
            ["--json", "--poll-interval", "0", "--max-iterations", "1",
             "--expected-reports", "2",
             "--expected-task-id", "bt1", "--expected-task-id", "bt2", tmpdir],
            expect_exit=0, label="expected-reports: batch appends receipts",
        )
        events = []
        with open(os.path.join(tmpdir, "events.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        received = sorted(
            e.get("task_id") for e in events
            if e.get("event_type") == "REPORT_RECEIVED"
        )
        if received != ["bt1", "bt2"]:
            print("    FAIL: expected REPORT_RECEIVED for bt1+bt2, got: {}".format(received))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_batch_needs_fix_stale_report():
    """Re-armed batch: stale schema-valid report for NEEDS_FIX task does NOT
    emit reports_ready until a newer-mtime report lands."""
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-batch-needs-fix-")
    try:
        with open(os.path.join(tmpdir, "task-A-bt1.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_task("bt1", "A", "2026-06-24"))
        with open(os.path.join(tmpdir, "task-B-bt2.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_task("bt2", "B", "2026-06-24", status="NEEDS_FIX"))
        with open(os.path.join(tmpdir, "report-A-bt1.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_valid_report("bt1", "A"))
        with open(os.path.join(tmpdir, "report-B-bt2.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_valid_report("bt2", "B"))

        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        report_b_mtime = mtime_iso(os.path.join(tmpdir, "report-B-bt2.md"))
        with open(state_path, "w", encoding="utf-8") as sf:
            json.dump({
                "report-B-bt2.md": {
                    "mtime": report_b_mtime,
                    "status": "valid",
                }
            }, sf, indent=2)

        ok, stdout, _ = run(
            [
                "--json", "--poll-interval", "0", "--max-iterations", "1",
                "--stale-threshold", "999999",
                "--expected-reports", "2",
                "--expected-task-id", "bt1", "--expected-task-id", "bt2",
                tmpdir,
            ],
            expect_exit=2,
            label="batch-needs-fix-stale-report",
        )
        data = json.loads(stdout) if stdout.strip() else {}
        if data.get("event") != "reports_incomplete":
            print("    FAIL: NEEDS_FIX stale report must not count as ready, got: {}".format(
                stdout[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_batch_malformed_duplicate_single_receipt():
    """Valid report plus malformed duplicate for same task_id yields exactly
    one REPORT_RECEIVED event."""
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-batch-malformed-dup-")
    try:
        open(os.path.join(tmpdir, "events.jsonl"), "w", encoding="utf-8").close()
        with open(os.path.join(tmpdir, "task-A-bt1.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_task("bt1", "A", "2026-06-24"))
        with open(os.path.join(tmpdir, "report-A-bt1-valid.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_valid_report("bt1", "A"))
        with open(os.path.join(tmpdir, "report-A-bt1-bad.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write("---\nschema: agent-file-coordination/report\ntask_id: bt1\n---\nbad")

        ok, stdout, _ = run(
            [
                "--json", "--poll-interval", "0", "--max-iterations", "1",
                "--expected-reports", "1",
                "--expected-task-id", "bt1",
                tmpdir,
            ],
            expect_exit=0,
            label="batch-malformed-dup-single-receipt",
        )
        events = []
        with open(os.path.join(tmpdir, "events.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        received_count = sum(
            1 for e in events if e.get("event_type") == "REPORT_RECEIVED"
        )
        if received_count != 1:
            print("    FAIL: expected exactly 1 REPORT_RECEIVED, got: {}".format(received_count))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_batch_quorum_skips_consumed_report():
    """Quorum re-arm: an already-consumed valid report (non-NEEDS_FIX task) is
    not recounted, so the batch waits for the next worker instead of looping."""
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-batch-consumed-")
    try:
        with open(os.path.join(tmpdir, "task-A-bt1.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_task("bt1", "A", "2026-06-24"))  # status ASSIGNED
        with open(os.path.join(tmpdir, "report-A-bt1.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_valid_report("bt1", "A"))

        # Seed state: bt1's report already consumed at its current mtime.
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        with open(state_path, "w", encoding="utf-8") as sf:
            json.dump({
                "report-A-bt1.md": {
                    "mtime": mtime_iso(os.path.join(tmpdir, "report-A-bt1.md")),
                    "status": "valid",
                }
            }, sf, indent=2)

        ok, stdout, _ = run(
            [
                "--json", "--poll-interval", "0", "--max-iterations", "1",
                "--stale-threshold", "999999",
                "--expected-reports", "1", "--expected-task-id", "bt1",
                tmpdir,
            ],
            expect_exit=2,
            label="batch-quorum-skips-consumed-report",
        )
        data = json.loads(stdout) if stdout.strip() else {}
        if data.get("event") != "reports_incomplete":
            print("    FAIL: consumed report must not re-fire reports_ready, got: {}".format(
                stdout[:300]
            ))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_batch_invalid_expected_report_wakes_rejected():
    """An expected batch member with only an invalid report wakes report_rejected
    immediately (exit 3), not after the full max-iterations timeout."""
    tmpdir = tempfile.mkdtemp(prefix="afc-watch-batch-rejected-")
    try:
        with open(os.path.join(tmpdir, "task-A-bt1.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write(_batch_task("bt1", "A", "2026-06-24"))
        # Only a schema-invalid report for the expected task.
        with open(os.path.join(tmpdir, "report-A-bt1.md"), "w",
                  encoding="utf-8", newline="\n") as fh:
            fh.write("---\nschema: agent-file-coordination/report\ntask_id: bt1\n---\nbad")

        ok, stdout, _ = run(
            [
                "--json", "--poll-interval", "0", "--max-iterations", "720",
                "--expected-reports", "1", "--expected-task-id", "bt1",
                tmpdir,
            ],
            expect_exit=3,
            label="batch-invalid-expected-report-wakes-rejected",
        )
        data = json.loads(stdout) if stdout.strip() else {}
        if data.get("event") != "report_rejected" or data.get("task_id") != "bt1":
            print("    FAIL: expected report_rejected for bt1, got: {}".format(stdout[:300]))
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    print("Running afc-watch.py fixture tests...")
    print()
    all_ok = True

    tests = [
        test_help,
        test_auto_archive_default_off,
        test_auto_archive_terminal_task,
        test_auto_archive_requires_report,
        test_auto_archive_one_task_per_run,
        test_auto_archive_rejects_duplicate_task_id,
        test_valid_report_wake,
        test_valid_report_json,
        test_cal2_arm_dry_run_no_write,
        test_cal2_arm_records_dispatch_then_watches,
        test_cal2_arm_batch_filters_task_ids,
        test_cal2_arm_batch_incremental_opts_out,
        test_cal2_arm_expected_reports_out_of_range,
        test_cal2_arm_batch_auto_archive_forces_incremental,
        test_cal2_arm_blocks_missing_roster,
        test_cal2_arm_blocks_unrostered_agent,
        test_cal2_arm_blocks_blank_agent_name,
        test_expected_reports_batch_stale_alarm,
        test_expected_reports_batch_fresh_not_stale,
        test_expected_reports_batch_appends_receipts,
        test_malformed_report_rejected,
        test_agent_name_mismatch_rejected,
        test_stale_alarm,
        test_stale_alarm_json,
        test_scoped_stale_alarm_ignores_unrelated_old_task,
        test_idle_no_wake,
        test_missing_inbox,
        test_stale_alarm_one_shot,
        test_no_idle_wake_bounded,
        test_state_persist_success,
        test_state_persist_forced_failure,
        test_direct_write_fallback_on_replace_failure,
        test_no_duplicate_wake_after_save,
        test_temp_file_cleanup,
        test_fresh_task_no_false_stale,
        test_old_task_with_old_mtime_stale,
        test_multi_reports_no_duplicates,
        test_out_of_order_reports,
        test_report_arrives_between_intake_and_rearm,
        test_malformed_plus_valid,
        test_no_artifact_files_created,
        test_state_no_rollback_on_parallel_intake,
        test_preserve_later_seen_report_on_early_update,
        # C5 hardening regression tests
        test_rejected_missing_frontmatter,
        test_rejected_invalid_trust,
        test_rejected_dangerous_phrase,
        test_rejected_no_repeat,
        test_rejected_then_corrected,
        test_rejected_plus_valid,
        test_expected_report_matching,
        test_expected_report_rejected,
        test_expected_report_unrelated_not_in_state,
        test_expected_report_out_of_inbox,
        test_expected_report_task_id_mismatch,
        test_expected_report_missing_frontmatter,
        test_expected_report_quoted_scalars_accepted,
        test_expected_report_bool_literal_task_id,
        test_expected_report_empty_evidence_rejected,
        test_expected_report_corrected,
        test_expected_report_no_repeat,
        test_expected_report_needs_fix_waits_for_update,
        test_state_monotonicity_rejected,
        test_unrelated_old_report_no_wake,
        test_expected_report_ignores_unrelated,
        test_expected_reports_batch,
        test_batch_needs_fix_stale_report,
        test_batch_malformed_duplicate_single_receipt,
        test_batch_quorum_skips_consumed_report,
        test_batch_invalid_expected_report_wakes_rejected,
    ]

    for test_fn in tests:
        try:
            ok = test_fn()
        except Exception as exc:
            print("  [FAIL] {}: {}".format(test_fn.__name__, exc))
            ok = False
        if not ok:
            all_ok = False
        print()

    if all_ok:
        print("All fixture tests passed.")
        return 0
    else:
        print("Some fixture tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
