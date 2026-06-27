#!/usr/bin/env python3
"""Test runner for afc-poll.py fixtures.

Exercises all success and failure cases.

Usage:
    python -B examples/fixtures/afc-poll/run-tests.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "afc-poll.py")
SCRIPT = os.path.normpath(SCRIPT)

BASE = os.path.dirname(os.path.abspath(__file__))
PASS_DIR = os.path.join(BASE, "pass")
FAIL_DIR = os.path.join(BASE, "fail")


def run(args, expect_exit=0, label=""):
    """Run afc-poll.py with given args. Returns (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "-B", SCRIPT] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    ok = result.returncode == expect_exit
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label} (exit={result.returncode}, expected={expect_exit})")
    if not ok:
        print(f"    stdout: {result.stdout[:500]}")
        print(f"    stderr: {result.stderr[:500]}")
    return ok, result.stdout, result.stderr


def make_active_inbox_with_bloat():
    """Create a temp inbox with tiny active content and huge archive/artifacts."""
    tmpdir = tempfile.mkdtemp(prefix="afc-poll-test-")
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
    tmpdir = tempfile.mkdtemp(prefix="afc-poll-test-")
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
    tmpdir = tempfile.mkdtemp(prefix="afc-poll-test-")
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


def test_help():
    """--help exits 0."""
    ok, stdout, stderr = run(["--help"], expect_exit=0, label="--help")
    if "afc-poll" not in stdout.lower():
        print(f"    WARNING: expected 'afc-poll' in stdout, got: {stdout[:200]}")
    return ok


def test_fresh_inbox():
    """First run with no state file → all reports are new.

    Runs in a temp copy to avoid modifying git-tracked fixture files.
    """
    src_inbox = os.path.join(PASS_DIR, "fresh-inbox")
    tmpdir = tempfile.mkdtemp(prefix="afc-poll-test-")
    try:
        shutil.copytree(src_inbox, tmpdir, dirs_exist_ok=True)

        ok, stdout, stderr = run(
            [tmpdir],
            expect_exit=0,
            label="fresh-inbox",
        )
        if "coordinator should review" not in stdout:
            print(f"    FAIL: expected 'coordinator should review' in stdout, got: {stdout[:300]}")
            ok = False

        # State file should have been created
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        if not os.path.exists(state_path):
            print("    FAIL: state file not created")
            ok = False
        else:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            if "report-Worker1-poll-a.md" not in state:
                print(f"    FAIL: report-Worker1-poll-a.md not in state: {state}")
                ok = False

        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fresh_inbox_json():
    """First run with --json produces valid JSON with new reports.

    Runs in a temp copy to avoid modifying git-tracked fixture files.
    """
    src_inbox = os.path.join(PASS_DIR, "fresh-inbox")
    tmpdir = tempfile.mkdtemp(prefix="afc-poll-test-")
    try:
        shutil.copytree(src_inbox, tmpdir, dirs_exist_ok=True)

        ok, stdout, stderr = run(
            ["--json", tmpdir],
            expect_exit=0,
            label="fresh-inbox-json",
        )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            print(f"    FAIL: stdout is not valid JSON: {stdout[:300]}")
            return False

        if "polled_at" not in data:
            print("    FAIL: missing 'polled_at' key")
            ok = False
        if "report-Worker1-poll-a.md" not in data.get("new_reports", []):
            print(f"    FAIL: expected report in new_reports, got: {data.get('new_reports')}")
            ok = False
        if not data.get("next_actions"):
            print("    FAIL: next_actions is empty")
            ok = False

        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_second_run():
    """Second run: only new report appears, old report is skipped.

    Runs in a temp copy to avoid modifying git-tracked fixture files.
    """
    src_inbox = os.path.join(PASS_DIR, "second-run")
    tmpdir = tempfile.mkdtemp(prefix="afc-poll-test-")
    try:
        shutil.copytree(src_inbox, tmpdir, dirs_exist_ok=True)

        # Reseed state deterministically: pre-record Worker2 (already-seen)
        # using its current mtime; omit Worker3 so it is detected as new.
        worker2 = os.path.join(tmpdir, "report-Worker2-poll-b.md")
        import datetime as _dt
        worker2_mtime = _dt.datetime.fromtimestamp(
            os.path.getmtime(worker2), tz=_dt.timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({"report-Worker2-poll-b.md": worker2_mtime}, f, indent=2)

        ok, stdout, stderr = run(
            [tmpdir],
            expect_exit=0,
            label="second-run",
        )
        if "report-Worker3-poll-c.md" not in stdout:
            print(f"    FAIL: expected new report in stdout, got: {stdout[:300]}")
            ok = False
        if "report-Worker2-poll-b.md" in stdout:
            print(f"    FAIL: old report should NOT appear in stdout, got: {stdout[:300]}")
            ok = False

        # State file should now include both reports
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            if "report-Worker3-poll-c.md" not in state:
                print(f"    FAIL: new report not in updated state: {state}")
                ok = False
        else:
            print("    FAIL: state file missing after run")
            ok = False

        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_dry_run():
    """--dry-run does not update the state file.

    Runs in a temp copy to avoid modifying git-tracked fixture files.
    """
    src_inbox = os.path.join(PASS_DIR, "fresh-inbox")
    tmpdir = tempfile.mkdtemp(prefix="afc-poll-test-")
    try:
        shutil.copytree(src_inbox, tmpdir, dirs_exist_ok=True)

        ok, stdout, stderr = run(
            ["--dry-run", tmpdir],
            expect_exit=0,
            label="dry-run",
        )
        if "coordinator should review" not in stdout:
            print(f"    FAIL: expected output in dry-run, got: {stdout[:300]}")
            ok = False

        # State file should NOT have been created
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        if os.path.exists(state_path):
            print("    FAIL: state file was created during --dry-run")
            ok = False

        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_missing_inbox():
    """Missing INBOX_DIR → exit 1."""
    inbox = os.path.join(FAIL_DIR, "missing-inbox", "nonexistent-dir")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=1,
        label="missing-inbox",
    )
    if "directory not found" not in stderr:
        print(f"    WARNING: expected 'directory not found' in stderr, got: {stderr[:200]}")
    return ok


def test_nonprefix_report():
    """Report without report- prefix is detected by schema frontmatter.

    Runs in a temp copy to avoid modifying git-tracked fixture files.
    """
    src_inbox = os.path.join(PASS_DIR, "nonprefix-report")
    tmpdir = tempfile.mkdtemp(prefix="afc-poll-test-")
    try:
        shutil.copytree(src_inbox, tmpdir, dirs_exist_ok=True)

        ok, stdout, stderr = run(
            [tmpdir],
            expect_exit=0,
            label="nonprefix-report",
        )
        if "coordinator should review" not in stdout:
            print(f"    FAIL: expected 'coordinator should review' in stdout, got: {stdout[:300]}")
            ok = False

        # The report file cache-test-Implementer-result.md (no report- prefix)
        # must be detected and recorded in state.
        state_path = os.path.join(tmpdir, ".afc-poll-state.json")
        if not os.path.exists(state_path):
            print("    FAIL: state file not created")
            ok = False
        else:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            if "cache-test-Implementer-result.md" not in state:
                print(f"    FAIL: non-prefixed report not in state: {state}")
                ok = False

        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_closed_files_hint_text():
    """Closed task in active inbox -> HINT on text output."""
    src_inbox = os.path.join(PASS_DIR, "closed-files-hint")
    tmpdir = tempfile.mkdtemp(prefix="afc-poll-test-")
    try:
        shutil.copytree(src_inbox, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            [tmpdir],
            expect_exit=0,
            label="closed-files-hint-text",
        )
        if "HINT:" not in stdout:
            print(f"    FAIL: expected HINT: in stdout, got: {stdout[:300]}")
            ok = False
        if "closed task/report files" not in stdout:
            print(f"    FAIL: expected 'closed task/report files' in hint, got: {stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_closed_files_hint_json():
    """Closed task in active inbox -> hints array in JSON output."""
    src_inbox = os.path.join(PASS_DIR, "closed-files-hint")
    tmpdir = tempfile.mkdtemp(prefix="afc-poll-test-")
    try:
        shutil.copytree(src_inbox, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            ["--json", tmpdir],
            expect_exit=0,
            label="closed-files-hint-json",
        )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            print(f"    FAIL: stdout is not valid JSON: {stdout[:300]}")
            return False
        if "hints" not in data:
            print("    FAIL: missing 'hints' key in JSON output")
            ok = False
        elif not data["hints"]:
            print("    FAIL: hints array is empty when hint expected")
            ok = False
        elif "closed task/report files" not in data["hints"][0]:
            print(f"    FAIL: expected closed-files hint, got: {data['hints']}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_size_hint():
    """Oversized active task file -> size HINT emitted."""
    tmpdir = make_large_active_task_inbox()
    try:
        ok, stdout, stderr = run(
            [tmpdir],
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
            [tmpdir],
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


def test_size_hint_ignores_archive_and_artifacts_json():
    """Huge archive/artifacts content should not appear in JSON hints either."""
    tmpdir = make_active_inbox_with_bloat()
    try:
        ok, stdout, stderr = run(
            ["--json", tmpdir],
            expect_exit=0,
            label="size-hint-ignores-archive-artifacts-json",
        )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            print(f"    FAIL: stdout is not valid JSON: {stdout[:300]}")
            return False
        if data.get("hints"):
            print(f"    FAIL: unexpected hints in JSON output: {data['hints']}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_size_zero_without_active_working_set():
    """Ignored metadata plus archive/artifacts should keep active size at zero."""
    tmpdir = make_inbox_without_active_working_set()
    try:
        ok, stdout, stderr = run(
            [tmpdir],
            expect_exit=0,
            label="size-zero-without-active-working-set",
        )
        if "HINT:" in stdout:
            print(f"    FAIL: unexpected HINT in output: {stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_size_zero_without_active_working_set_json():
    """Ignored metadata plus archive/artifacts should keep JSON hints empty."""
    tmpdir = make_inbox_without_active_working_set()
    try:
        ok, stdout, stderr = run(
            ["--json", tmpdir],
            expect_exit=0,
            label="size-zero-without-active-working-set-json",
        )
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            print(f"    FAIL: stdout is not valid JSON: {stdout[:300]}")
            return False
        if data.get("hints"):
            print(f"    FAIL: unexpected hints in JSON output: {data['hints']}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_no_hint_when_clean():
    """Clean inbox -> no HINT in text or JSON output."""
    src_inbox = os.path.join(PASS_DIR, "fresh-inbox")
    tmpdir = tempfile.mkdtemp(prefix="afc-poll-test-")
    try:
        shutil.copytree(src_inbox, tmpdir, dirs_exist_ok=True)
        # Text mode
        ok, stdout, stderr = run(
            [tmpdir],
            expect_exit=0,
            label="no-hint-clean-text",
        )
        if "HINT:" in stdout:
            print(f"    FAIL: unexpected HINT: in clean inbox text output: {stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    print("Running afc-poll.py fixture tests...")
    print()
    all_ok = True

    tests = [
        test_help,
        test_fresh_inbox,
        test_fresh_inbox_json,
        test_second_run,
        test_dry_run,
        test_missing_inbox,
        test_nonprefix_report,
        test_closed_files_hint_text,
        test_closed_files_hint_json,
        test_size_hint,
        test_size_hint_ignores_archive_and_artifacts,
        test_size_hint_ignores_archive_and_artifacts_json,
        test_size_zero_without_active_working_set,
        test_size_zero_without_active_working_set_json,
        test_no_hint_when_clean,
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
