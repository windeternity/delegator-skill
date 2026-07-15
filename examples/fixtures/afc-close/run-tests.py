#!/usr/bin/env python3
"""Test runner for afc-close.py fixtures."""

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "afc-close.py"))
VALIDATOR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "validate-agent-inbox.py"))
BASE = os.path.dirname(os.path.abspath(__file__))
PASS_DIR = os.path.join(BASE, "pass")


def load_close_module():
    scripts_dir = os.path.dirname(SCRIPT)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("afc_close", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(args, expect_exit=0, label=""):
    result = subprocess.run([sys.executable, "-B", SCRIPT] + args, capture_output=True, text=True)
    ok = result.returncode == expect_exit
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {label} (exit={result.returncode}, expected={expect_exit})")
    if not ok:
        print(f"    stdout: {result.stdout[:300]}")
        print(f"    stderr: {result.stderr[:300]}")
    return ok, result.stdout, result.stderr


def test_dry_run_no_move():
    src = os.path.join(PASS_DIR, "single-task")
    tmpdir = tempfile.mkdtemp(prefix="afc-close-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, _ = run(
            ["--dry-run", "--task-id", "alpha", "--status", "CLOSED_GO", tmpdir],
            label="dry-run-no-move",
        )
        if "Would update task status" not in stdout:
            print(f"    FAIL: expected dry-run summary, got: {stdout[:300]}")
            ok = False
        if not os.path.exists(os.path.join(tmpdir, "task-Worker-alpha.md")):
            print("    FAIL: task moved during dry-run")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_close_moves_and_events():
    src = os.path.join(PASS_DIR, "single-task")
    tmpdir = tempfile.mkdtemp(prefix="afc-close-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, _ = run(
            ["--task-id", "alpha", "--status", "CLOSED_GO", tmpdir],
            label="close-moves-and-events",
        )
        if not ok:
            return False
        if os.path.exists(os.path.join(tmpdir, "task-Worker-alpha.md")):
            print("    FAIL: active task still exists after close")
            ok = False
        archive_root = os.path.join(tmpdir, "archive")
        archived_task = None
        for root, _, files in os.walk(archive_root):
            if "task-Worker-alpha.md" in files:
                archived_task = os.path.join(root, "task-Worker-alpha.md")
        if not archived_task:
            print("    FAIL: archived task not found")
            ok = False
        else:
            with open(archived_task, "r", encoding="utf-8") as f:
                if "status: CLOSED_GO" not in f.read():
                    print("    FAIL: archived task status was not updated")
                    ok = False
        with open(os.path.join(tmpdir, "events.jsonl"), "r", encoding="utf-8") as f:
            if "TASK_CLOSED" not in f.read():
                print("    FAIL: TASK_CLOSED event not appended")
                ok = False
        result = subprocess.run([sys.executable, "-B", VALIDATOR, tmpdir], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"    FAIL: validator failed: {result.stdout[:300]} {result.stderr[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_move_failure_rolls_back():
    tmpdir = tempfile.mkdtemp(prefix="afc-close-rollback-test-")
    module = load_close_module()
    original_rename = module.os.rename
    try:
        sources = [os.path.join(tmpdir, "one.md"), os.path.join(tmpdir, "two.md")]
        archive_dir = os.path.join(tmpdir, "archive")
        os.makedirs(archive_dir)
        for path in sources:
            with open(path, "w", encoding="utf-8") as f:
                f.write(path)
        destinations = [(path, os.path.join(archive_dir, os.path.basename(path))) for path in sources]
        calls = {"count": 0}

        def fail_second_move(src, dest):
            calls["count"] += 1
            if calls["count"] == 2:
                raise PermissionError("simulated lock")
            return original_rename(src, dest)

        module.os.rename = fail_second_move
        try:
            module.move_files_transactionally(destinations)
            print("    FAIL: expected simulated move failure")
            return False
        except PermissionError:
            pass
        finally:
            module.os.rename = original_rename

        ok = all(os.path.exists(path) for path in sources)
        ok = ok and all(not os.path.exists(dest) for _, dest in destinations)
        tag = "PASS" if ok else "FAIL"
        print(f"  [{tag}] move-failure-rolls-back")
        return ok
    finally:
        module.os.rename = original_rename
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_event_append_failure_rolls_back_close():
    src = os.path.join(PASS_DIR, "single-task")
    tmpdir = tempfile.mkdtemp(prefix="afc-close-event-rollback-")
    module = load_close_module()
    original_argv = sys.argv[:]
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        task_path = os.path.join(tmpdir, "task-Worker-alpha.md")
        with open(task_path, "r", encoding="utf-8") as handle:
            original = handle.read()
        module.append_event_once = lambda *args, **kwargs: (_ for _ in ()).throw(OSError("simulated append failure"))
        sys.argv = [SCRIPT, "--task-id", "alpha", "--status", "CLOSED_GO", tmpdir]
        rc = module.main()
        archived = any("task-Worker-alpha.md" in files for _, _, files in os.walk(os.path.join(tmpdir, "archive")))
        with open(task_path, "r", encoding="utf-8") as handle:
            restored = handle.read()
        ok = rc == 1 and not archived and restored == original
        print("  [{}] event-append-failure-rolls-back-close".format("PASS" if ok else "FAIL"))
        return ok
    finally:
        sys.argv = original_argv
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    print("Running afc-close.py fixture tests...")
    print()
    all_ok = True
    for test_fn in [test_dry_run_no_move, test_close_moves_and_events, test_move_failure_rolls_back,
                    test_event_append_failure_rolls_back_close]:
        try:
            ok = test_fn()
        except Exception as exc:
            print(f"  [FAIL] {test_fn.__name__}: {exc}")
            ok = False
        if not ok:
            all_ok = False
        print()
    if all_ok:
        print("All afc-close fixture tests passed.")
        return 0
    print("Some afc-close fixture tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
