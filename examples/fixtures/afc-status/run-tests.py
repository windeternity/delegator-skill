#!/usr/bin/env python3
"""Test runner for afc-status.py fixtures.

Exercises all success and failure cases, then runs validation on the
write-mode generated STATUS.md and events.jsonl.

Usage:
    python -B examples/fixtures/afc-status/run-tests.py
"""

import difflib
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "afc-status.py")
SCRIPT = os.path.normpath(SCRIPT)

BASE = os.path.dirname(os.path.abspath(__file__))
PASS_DIR = os.path.join(BASE, "pass")
FAIL_DIR = os.path.join(BASE, "fail")

UPDATED_AT = "2026-06-08"


def run(args, expect_exit=0, label=""):
    """Run afc-status.py with given args. Returns (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "-B", SCRIPT] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    ok = result.returncode == expect_exit
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label} (exit={result.returncode}, expected={expect_exit})")
    if not ok:
        print(f"    stdout: {result.stdout[:300]}")
        print(f"    stderr: {result.stderr[:300]}")
    return ok, result.stdout, result.stderr


def make_active_inbox_with_bloat():
    """Create a temp inbox with tiny active content and huge archive/artifacts."""
    tmpdir = tempfile.mkdtemp(prefix="afc-status-test-")
    task_path = os.path.join(tmpdir, "task-Worker-active.md")
    with open(task_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(
            """---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: active-task
agent_name: Worker
role: implementer
protocol_mode: task-only
coordinator_authority: no
status: RUNNING
permission_scope:
  read_files: yes
  write_reports: yes
  write_task_files: no
  modify_source: no
  run_commands: none
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: read_only_shared
  path: <PROJECT_ROOT>
  may_create_worktree: no
validation_tier: no-test-needed
report_path: <PROJECT_ROOT>/.agent-inbox/active-task-Worker.md
created_at: 2026-06-08
---

# Active task
"""
        )

    archive_dir = os.path.join(tmpdir, "archive", "2026-06")
    artifacts_dir = os.path.join(tmpdir, "artifacts", "active-task")
    os.makedirs(archive_dir)
    os.makedirs(artifacts_dir)
    for path in [
        os.path.join(archive_dir, "archived-note.md"),
        os.path.join(artifacts_dir, "artifact-log.md"),
    ]:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("---\n")
            f.write("x" * (120 * 1024))
            f.write("\n")
    return tmpdir


def make_inbox_without_active_working_set():
    """Create a temp inbox with only ignored metadata and large archive/artifacts."""
    tmpdir = tempfile.mkdtemp(prefix="afc-status-test-")
    files = {
        "events.jsonl": "{\"event_type\":\"NOOP\",\"payload\":\"" + ("x" * (120 * 1024)) + "\"}\n",
        "STATUS.txt": "status cache\n" + ("x" * (40 * 1024)),
        "roster.json": "{\"agents\":[]}\n" + ("x" * (40 * 1024)),
        "locks.lock": "locked\n" + ("x" * (40 * 1024)),
        "spec.txt": "spec\n" + ("x" * (40 * 1024)),
        "tmp.bin": "tmp\n" + ("x" * (40 * 1024)),
    }
    for rel_path, content in files.items():
        path = os.path.join(tmpdir, rel_path)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    archive_dir = os.path.join(tmpdir, "archive", "2026-06")
    artifacts_dir = os.path.join(tmpdir, "artifacts", "task-1")
    os.makedirs(archive_dir)
    os.makedirs(artifacts_dir)
    for path in [
        os.path.join(archive_dir, "archived-note.md"),
        os.path.join(artifacts_dir, "artifact-log.md"),
    ]:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write("---\n")
            f.write("x" * (120 * 1024))
            f.write("\n")
    return tmpdir


def make_large_active_task_inbox():
    """Create a temp inbox with a single oversized active task file."""
    tmpdir = tempfile.mkdtemp(prefix="afc-status-test-")
    task_path = os.path.join(tmpdir, "task-Worker-large.md")
    with open(task_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(
            """---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: large-task
agent_name: Worker
role: implementer
protocol_mode: task-only
coordinator_authority: no
status: RUNNING
permission_scope:
  read_files: yes
  write_reports: yes
  write_task_files: no
  modify_source: no
  run_commands: none
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: read_only_shared
  path: <PROJECT_ROOT>
  may_create_worktree: no
validation_tier: no-test-needed
report_path: <PROJECT_ROOT>/.agent-inbox/large-task-Worker.md
created_at: 2026-06-08
---

# Large active task
"""
            + ("x" * (120 * 1024))
        )
    return tmpdir


def test_assigned_no_report():
    """Assigned task without report -> ASSIGNED / wait_for_report."""
    inbox = os.path.join(PASS_DIR, "assigned-no-report")
    ok, stdout, stderr = run(
        ["--dry-run", "--updated-at", UPDATED_AT, inbox],
        expect_exit=0,
        label="assigned-no-report",
    )
    assert "task-alpha" in stdout, "task-alpha missing from output"
    assert "ASSIGNED" in stdout, "ASSIGNED status missing"
    assert "wait_for_report" in stdout, "wait_for_report missing"
    return ok


def test_task_with_report():
    """Task with matching report -> REPORTED / coordinator_review."""
    inbox = os.path.join(PASS_DIR, "task-with-report")
    ok, stdout, stderr = run(
        ["--dry-run", "--updated-at", UPDATED_AT, inbox],
        expect_exit=0,
        label="task-with-report",
    )
    assert "task-beta" in stdout, "task-beta missing from output"
    assert "REPORTED" in stdout, "REPORTED status missing"
    assert "coordinator_review" in stdout, "coordinator_review missing"
    return ok


def test_dry_run_deterministic():
    """Dry-run output matches expected snapshot."""
    inbox = os.path.join(PASS_DIR, "dry-run")
    expected_path = os.path.join(inbox, "expected-stdout.txt")
    with open(expected_path, "r", encoding="utf-8") as f:
        expected = f.read().strip()

    ok, stdout, stderr = run(
        ["--dry-run", "--updated-at", UPDATED_AT, inbox],
        expect_exit=0,
        label="dry-run-deterministic",
    )
    actual = stdout.strip()
    if actual != expected:
        print("    Dry-run output mismatch:")
        diff = difflib.unified_diff(expected.splitlines(), actual.splitlines(), lineterm="")
        for line in diff:
            print(f"    {line}")
        return False
    return ok


def test_write_mode():
    """Write mode produces validator-clean STATUS.md and events.jsonl.

    Runs in a temp copy of the fixture directory to avoid modifying
    git-tracked fixture files, which causes ``[WinError 5] Access denied``
    on Windows when those files are read-only or held by another process.
    """
    src_inbox = os.path.join(PASS_DIR, "write-mode")
    tmpdir = tempfile.mkdtemp(prefix="afc-status-test-")
    try:
        shutil.copytree(src_inbox, tmpdir, dirs_exist_ok=True)

        ok, stdout, stderr = run(
            ["--updated-at", UPDATED_AT, tmpdir],
            expect_exit=0,
            label="write-mode",
        )
        if not ok:
            return False

        status_path = os.path.join(tmpdir, "STATUS.md")
        events_path = os.path.join(tmpdir, "events.jsonl")

        if not os.path.exists(status_path):
            print("    FAIL: STATUS.md not created")
            return False
        if not os.path.exists(events_path):
            print("    FAIL: events.jsonl not created")
            return False

        # Validate with the repo validator
        validator = os.path.join(os.path.dirname(SCRIPT), "validate-agent-inbox.py")
        for target, label in [(status_path, "STATUS.md validation"), (events_path, "events.jsonl validation")]:
            r = subprocess.run([sys.executable, "-B", validator, target], capture_output=True, text=True)
            status = "PASS" if r.returncode == 0 else "FAIL"
            print(f"  [{status}] {label} (exit={r.returncode})")
            if r.returncode != 0:
                print(f"    stdout: {r.stdout[:300]}")
                print(f"    stderr: {r.stderr[:300]}")
                ok = False

        # Verify event content
        with open(events_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "STATUS_UPDATED" not in content:
            print("    FAIL: STATUS_UPDATED event not found in events.jsonl")
            ok = False

        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_duplicate_task_id():
    """Duplicate task_id -> exit 1."""
    inbox = os.path.join(FAIL_DIR, "duplicate-task-id")
    ok, stdout, stderr = run(
        ["--dry-run", "--updated-at", UPDATED_AT, inbox],
        expect_exit=1,
        label="duplicate-task-id",
    )
    # Error message should be on stderr
    if "duplicate" not in stderr.lower():
        print(f"    WARNING: expected 'duplicate' in stderr, got: {stderr[:200]}")
    return ok


def test_orphan_report():
    """Report for unknown task_id -> exit 1."""
    inbox = os.path.join(FAIL_DIR, "orphan-report")
    ok, stdout, stderr = run(
        ["--dry-run", "--updated-at", UPDATED_AT, inbox],
        expect_exit=1,
        label="orphan-report",
    )
    if "orphan" not in stderr.lower():
        print(f"    WARNING: expected 'orphan' in stderr, got: {stderr[:200]}")
    return ok


def test_malformed_frontmatter():
    """Malformed frontmatter -> exit 1."""
    inbox = os.path.join(FAIL_DIR, "malformed-frontmatter")
    ok, stdout, stderr = run(
        ["--dry-run", "--updated-at", UPDATED_AT, inbox],
        expect_exit=1,
        label="malformed-frontmatter",
    )
    if "malformed" not in stderr.lower() and "error" not in stderr.lower():
        print(f"    WARNING: expected error in stderr, got: {stderr[:200]}")
    return ok


def test_missing_workspace_path():
    """Task missing workspace.path -> exit 1, no STATUS.md written.

    Runs in a temp copy to avoid modifying git-tracked fixture files.
    """
    src_inbox = os.path.join(FAIL_DIR, "missing-workspace-path")
    tmpdir = tempfile.mkdtemp(prefix="afc-status-test-")
    try:
        shutil.copytree(src_inbox, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--updated-at", UPDATED_AT, tmpdir],
            expect_exit=1,
            label="missing-workspace-path",
        )
        if "workspace.path" not in stderr:
            print(f"    WARNING: expected 'workspace.path' in stderr, got: {stderr[:200]}")
        # STATUS.md must NOT have been created
        status_path = os.path.join(tmpdir, "STATUS.md")
        if os.path.exists(status_path):
            print("    FAIL: STATUS.md was written despite validation failure")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_closed_files_hint():
    """Closed task in active inbox -> HINT emitted."""
    inbox = os.path.join(PASS_DIR, "closed-files-hint")
    ok, stdout, stderr = run(
        ["--dry-run", "--updated-at", UPDATED_AT, inbox],
        expect_exit=0,
        label="closed-files-hint",
    )
    if "HINT:" not in stdout:
        print(f"    FAIL: expected HINT: in stdout, got: {stdout[:300]}")
        ok = False
    if "closed task/report files" not in stdout:
        print(f"    FAIL: expected 'closed task/report files' in hint, got: {stdout[:300]}")
        ok = False
    return ok


def test_size_hint():
    """Oversized active task file -> size HINT emitted."""
    tmpdir = make_large_active_task_inbox()
    try:
        ok, stdout, stderr = run(
            ["--dry-run", "--updated-at", UPDATED_AT, tmpdir],
            expect_exit=0,
            label="size-hint",
        )
        if "HINT:" not in stdout:
            print(f"    FAIL: expected HINT: in stdout, got: {stdout[:300]}")
            ok = False
        if "active inbox is" not in stdout or "KB" not in stdout:
            print(f"    FAIL: expected size hint, got: {stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_size_hint_ignores_archive_and_artifacts():
    """Huge archive/artifacts content should not trigger active inbox size hint."""
    tmpdir = make_active_inbox_with_bloat()
    try:
        ok, stdout, stderr = run(
            ["--dry-run", "--updated-at", UPDATED_AT, tmpdir],
            expect_exit=0,
            label="size-hint-ignores-archive-artifacts",
        )
        if "HINT: active inbox is" in stdout:
            print(f"    FAIL: size hint should ignore archive/artifacts, got: {stdout[:300]}")
            ok = False
        if "HINT:" in stdout:
            print(f"    FAIL: unexpected HINT in output: {stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_size_zero_without_active_working_set():
    """Ignored metadata plus archive/artifacts should keep active size at zero."""
    tmpdir = make_inbox_without_active_working_set()
    try:
        ok, stdout, stderr = run(
            ["--dry-run", "--updated-at", UPDATED_AT, tmpdir],
            expect_exit=0,
            label="size-zero-without-active-working-set",
        )
        if "HINT:" in stdout:
            print(f"    FAIL: unexpected HINT in output: {stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_no_hint_when_clean():
    """Clean inbox (no closed files, under size threshold) -> no HINT emitted."""
    inbox = os.path.join(PASS_DIR, "dry-run")
    ok, stdout, stderr = run(
        ["--dry-run", "--updated-at", UPDATED_AT, inbox],
        expect_exit=0,
        label="no-hint-clean-inbox",
    )
    if "HINT:" in stdout:
        print(f"    FAIL: unexpected HINT: in clean inbox output: {stdout[:300]}")
        ok = False
    return ok


def test_stale_undispatched_hint():
    """Old ASSIGNED task without TASK_DISPATCHED -> J1 HINT emitted."""
    tmpdir = tempfile.mkdtemp(prefix="afc-status-test-")
    try:
        task_path = os.path.join(tmpdir, "task-Worker-stale-dispatch.md")
        with open(task_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(
                """---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: stale-dispatch
agent_name: Worker
role: implementer
protocol_mode: task-only
coordinator_authority: no
status: ASSIGNED
permission_scope:
  read_files: yes
  write_reports: yes
  write_task_files: no
  modify_source: no
  run_commands: none
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: read_only_shared
  path: <PROJECT_ROOT>
  may_create_worktree: no
validation_tier: no-test-needed
report_path: <PROJECT_ROOT>/.agent-inbox/stale-dispatch-Worker.md
created_at: 2026-06-08
---

# Stale undispatched task
"""
            )
        ok, stdout, stderr = run(
            ["--dry-run", "--updated-at", "2026-06-12", tmpdir],
            expect_exit=0,
            label="stale-undispatched-hint",
        )
        if "HINT: 1 ASSIGNED task(s) without dispatch confirmation" not in stdout:
            print(f"    FAIL: expected stale-undispatched HINT, got: {stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_summary_only_no_write():
    """--summary-only is read-only and does not create STATUS.md."""
    src_inbox = os.path.join(PASS_DIR, "assigned-no-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-status-test-")
    try:
        shutil.copytree(src_inbox, tmpdir, dirs_exist_ok=True)
        status_path = os.path.join(tmpdir, "STATUS.md")
        if os.path.exists(status_path):
            os.remove(status_path)
        ok, stdout, stderr = run(
            ["--summary-only", "--updated-at", UPDATED_AT, tmpdir],
            expect_exit=0,
            label="summary-only-no-write",
        )
        if "active_tasks:" not in stdout:
            print(f"    FAIL: expected summary output, got: {stdout[:300]}")
            ok = False
        if os.path.exists(status_path):
            print("    FAIL: STATUS.md was written in summary-only mode")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_budget_warning():
    """Oversized task files produce advisory warnings, not failures."""
    tmpdir = tempfile.mkdtemp(prefix="afc-status-test-")
    try:
        task_path = os.path.join(tmpdir, "task-Worker-large.md")
        with open(task_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(
                """---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: large-task
agent_name: Worker
role: implementer
protocol_mode: task-only
coordinator_authority: no
status: ASSIGNED
permission_scope:
  read_files: yes
  write_reports: yes
  write_task_files: no
  modify_source: no
  run_commands: none
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: read_only_shared
  path: <PROJECT_ROOT>
  may_create_worktree: no
validation_tier: no-test-needed
report_path: <PROJECT_ROOT>/.agent-inbox/report-large.md
created_at: 2026-06-08
---

# Large task
"""
                + ("x" * 3800)
            )
        ok, stdout, stderr = run(
            ["--summary-only", "--updated-at", UPDATED_AT, tmpdir],
            expect_exit=0,
            label="budget-warning",
        )
        if "WARN:" not in stdout or "task file(s) exceed" not in stdout:
            print(f"    FAIL: expected budget warning, got: {stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    print("Running afc-status.py fixture tests...")
    print()
    all_ok = True

    tests = [
        test_assigned_no_report,
        test_task_with_report,
        test_dry_run_deterministic,
        test_write_mode,
        test_duplicate_task_id,
        test_orphan_report,
        test_malformed_frontmatter,
        test_missing_workspace_path,
        test_closed_files_hint,
        test_size_hint,
        test_size_hint_ignores_archive_and_artifacts,
        test_size_zero_without_active_working_set,
        test_no_hint_when_clean,
        test_stale_undispatched_hint,
        test_summary_only_no_write,
        test_budget_warning,
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
    else:
        print("Some fixture tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
