#!/usr/bin/env python3
"""Test runner for afc-snapshot.py fixtures."""

import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "afc-snapshot.py"))
BASE = os.path.dirname(os.path.abspath(__file__))
PASS_DIR = os.path.join(BASE, "pass")


def run(args, expect_exit=0, label=""):
    result = subprocess.run([sys.executable, "-B", SCRIPT] + args, capture_output=True, text=True)
    ok = result.returncode == expect_exit
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {label} (exit={result.returncode}, expected={expect_exit})")
    if not ok:
        print(f"    stdout: {result.stdout[:300]}")
        print(f"    stderr: {result.stderr[:300]}")
    return ok, result.stdout, result.stderr


def make_active_inbox_with_bloat():
    """Create a temp inbox with tiny active content and huge archive/artifacts."""
    tmpdir = tempfile.mkdtemp(prefix="afc-snapshot-test-")
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
    return tmpdir, task_path


def make_inbox_without_active_working_set():
    """Create a temp inbox with only ignored metadata and large archive/artifacts."""
    tmpdir = tempfile.mkdtemp(prefix="afc-snapshot-test-")
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


def test_text_snapshot():
    inbox = os.path.join(PASS_DIR, "basic")
    ok, stdout, _ = run([inbox], label="text-snapshot")
    for expected in [
        "active_tasks: 1",
        "reports_waiting_for_review: 1",
        "closed_but_unarchived_tasks: 1",
        "recommended_next_action: review_reports",
    ]:
        if expected not in stdout:
            print(f"    FAIL: missing {expected!r}")
            ok = False
    return ok


def test_json_snapshot():
    inbox = os.path.join(PASS_DIR, "basic")
    ok, stdout, _ = run(["--json", inbox], label="json-snapshot")
    if not ok:
        return False
    data = json.loads(stdout)
    return (
        data["recommended_next_action"] == "review_reports"
        and len(data["active_tasks"]) == 1
        and len(data["reports_waiting_for_review"]) == 1
        and len(data["closed_but_unarchived_tasks"]) == 1
    )


def test_brief_snapshot():
    inbox = os.path.join(PASS_DIR, "basic")
    ok, stdout, _ = run(["--brief", inbox], label="brief-snapshot")
    if "active_tasks=1" not in stdout or "next=review_reports" not in stdout:
        print(f"    FAIL: unexpected brief output: {stdout[:300]}")
        ok = False
    return ok


def test_active_size_ignores_archive_and_artifacts():
    tmpdir, task_path = make_active_inbox_with_bloat()
    try:
        ok, stdout, _ = run(["--json", tmpdir], label="active-size-ignores-archive-artifacts")
        if not ok:
            return False
        data = json.loads(stdout)
        expected_size = os.path.getsize(task_path)
        if data["active_inbox_size_bytes"] != expected_size:
            print(
                "    FAIL: active_inbox_size_bytes={}, expected {}".format(
                    data["active_inbox_size_bytes"], expected_size
                )
            )
            return False
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_active_size_zero_without_active_working_set():
    tmpdir = make_inbox_without_active_working_set()
    try:
        ok, stdout, _ = run(["--json", tmpdir], label="active-size-zero-without-active-working-set")
        if not ok:
            return False
        data = json.loads(stdout)
        if data["active_inbox_size_bytes"] != 0:
            print(
                "    FAIL: active_inbox_size_bytes={}, expected 0".format(
                    data["active_inbox_size_bytes"]
                )
            )
            return False
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    print("Running afc-snapshot.py fixture tests...")
    print()
    all_ok = True
    for test_fn in [
        test_text_snapshot,
        test_json_snapshot,
        test_brief_snapshot,
        test_active_size_ignores_archive_and_artifacts,
        test_active_size_zero_without_active_working_set,
    ]:
        try:
            ok = test_fn()
        except Exception as exc:
            print(f"  [FAIL] {test_fn.__name__}: {exc}")
            ok = False
        if not ok:
            all_ok = False
        print()
    if all_ok:
        print("All afc-snapshot fixture tests passed.")
        return 0
    print("Some afc-snapshot fixture tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
