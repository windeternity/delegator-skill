#!/usr/bin/env python3
"""Test runner for afc-next.py fixtures.

Exercises all success, failure, and boundary cases.

Usage:
    python -B examples/fixtures/afc-next/run-tests.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "afc-next.py")
SCRIPT = os.path.normpath(SCRIPT)

BASE = os.path.dirname(os.path.abspath(__file__))
PASS_DIR = os.path.join(BASE, "pass")
FAIL_DIR = os.path.join(BASE, "fail")


def run(args, expect_exit=0, label=""):
    """Run afc-next.py with given args. Returns (exit_code, stdout, stderr)."""
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
    """--help exits 0 and mentions the decision order."""
    ok, stdout, stderr = run(["--help"], expect_exit=0, label="--help")
    if "afc-next" not in stdout.lower():
        print(f"    WARNING: expected 'afc-next' in stdout, got: {stdout[:200]}")
        ok = False
    if "RECOMMEND_REVIEW" not in stdout:
        print(f"    WARNING: expected 'RECOMMEND_REVIEW' in stdout")
        ok = False
    return ok


def test_report_exists():
    """Report exists for active task -> RECOMMEND_REVIEW."""
    inbox = os.path.join(PASS_DIR, "report-exists")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=0,
        label="report-exists",
    )
    if "RECOMMEND_REVIEW" not in stdout:
        print(f"    FAIL: expected 'RECOMMEND_REVIEW' in stdout, got: {stdout[:300]}")
        ok = False
    if "task-review" not in stdout:
        print(f"    FAIL: expected 'task-review' in stdout, got: {stdout[:300]}")
        ok = False
    return ok


def test_report_exists_json():
    """Report exists with --json produces valid JSON with RECOMMEND_REVIEW."""
    inbox = os.path.join(PASS_DIR, "report-exists")
    ok, stdout, stderr = run(
        ["--json", inbox],
        expect_exit=0,
        label="report-exists-json",
    )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print(f"    FAIL: stdout is not valid JSON: {stdout[:300]}")
        return False

    if data.get("action") != "RECOMMEND_REVIEW":
        print(f"    FAIL: expected action RECOMMEND_REVIEW, got: {data.get('action')}")
        ok = False
    if data.get("task_id") != "task-review":
        print(f"    FAIL: expected task_id 'task-review', got: {data.get('task_id')}")
        ok = False
    if "active_tasks" not in data:
        print(f"    FAIL: expected 'active_tasks' key")
        ok = False
    return ok


def test_draft_task():
    """DRAFT task -> RECOMMEND_ASSIGN."""
    inbox = os.path.join(PASS_DIR, "draft-task")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=0,
        label="draft-task",
    )
    if "RECOMMEND_ASSIGN" not in stdout:
        print(f"    FAIL: expected 'RECOMMEND_ASSIGN' in stdout, got: {stdout[:300]}")
        ok = False
    if "task-draft" not in stdout:
        print(f"    FAIL: expected 'task-draft' in stdout, got: {stdout[:300]}")
        ok = False
    return ok


def test_assigned_no_report():
    """ASSIGNED task with no report -> RECOMMEND_WAIT."""
    inbox = os.path.join(PASS_DIR, "assigned-no-report")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=0,
        label="assigned-no-report",
    )
    if "RECOMMEND_WAIT" not in stdout:
        print(f"    FAIL: expected 'RECOMMEND_WAIT' in stdout, got: {stdout[:300]}")
        ok = False
    if "task-wait" not in stdout:
        print(f"    FAIL: expected 'task-wait' in stdout, got: {stdout[:300]}")
        ok = False
    return ok


def test_running_no_report():
    """RUNNING task with no report -> RECOMMEND_WAIT."""
    inbox = os.path.join(PASS_DIR, "running-no-report")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=0,
        label="running-no-report",
    )
    if "RECOMMEND_WAIT" not in stdout:
        print(f"    FAIL: expected 'RECOMMEND_WAIT' in stdout, got: {stdout[:300]}")
        ok = False
    if "task-running" not in stdout:
        print(f"    FAIL: expected 'task-running' in stdout, got: {stdout[:300]}")
        ok = False
    return ok


def test_needs_fix():
    """NEEDS_FIX task -> RECOMMEND_REPAIR_REVIEW."""
    inbox = os.path.join(PASS_DIR, "needs-fix")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=0,
        label="needs-fix",
    )
    if "RECOMMEND_REPAIR_REVIEW" not in stdout:
        print(f"    FAIL: expected 'RECOMMEND_REPAIR_REVIEW' in stdout, got: {stdout[:300]}")
        ok = False
    if "task-fix" not in stdout:
        print(f"    FAIL: expected 'task-fix' in stdout, got: {stdout[:300]}")
        ok = False
    return ok


def test_closed_only():
    """All tasks closed -> NO_ACTION."""
    inbox = os.path.join(PASS_DIR, "closed-only")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=0,
        label="closed-only",
    )
    if "NO_ACTION" not in stdout:
        print(f"    FAIL: expected 'NO_ACTION' in stdout, got: {stdout[:300]}")
        ok = False
    return ok


def test_multi_active():
    """Multiple active tasks: report exists takes priority over DRAFT/ASSIGNED."""
    inbox = os.path.join(PASS_DIR, "multi-active")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=0,
        label="multi-active",
    )
    # task-beta has a report, task-alpha is DRAFT
    # Report takes priority (rule 2 > rule 3)
    if "RECOMMEND_REVIEW" not in stdout:
        print(f"    FAIL: expected 'RECOMMEND_REVIEW' in stdout, got: {stdout[:300]}")
        ok = False
    if "task-beta" not in stdout:
        print(f"    FAIL: expected 'task-beta' in stdout, got: {stdout[:300]}")
        ok = False
    return ok


def test_multi_active_json():
    """Multi-active with JSON shows correct counts."""
    inbox = os.path.join(PASS_DIR, "multi-active")
    ok, stdout, stderr = run(
        ["--json", inbox],
        expect_exit=0,
        label="multi-active-json",
    )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print(f"    FAIL: stdout is not valid JSON: {stdout[:300]}")
        return False

    if data.get("action") != "RECOMMEND_REVIEW":
        print(f"    FAIL: expected action RECOMMEND_REVIEW, got: {data.get('action')}")
        ok = False
    if data.get("task_id") != "task-beta":
        print(f"    FAIL: expected task_id 'task-beta', got: {data.get('task_id')}")
        ok = False
    if data.get("active_tasks") != 2:
        print(f"    FAIL: expected active_tasks 2, got: {data.get('active_tasks')}")
        ok = False
    if data.get("total_tasks") != 2:
        print(f"    FAIL: expected total_tasks 2, got: {data.get('total_tasks')}")
        ok = False
    return ok


def test_duplicate_task_id():
    """Duplicate task_id -> exit 1."""
    inbox = os.path.join(FAIL_DIR, "duplicate-task-id")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=1,
        label="duplicate-task-id",
    )
    if "duplicate" not in stderr.lower():
        print(f"    WARNING: expected 'duplicate' in stderr, got: {stderr[:200]}")
    return ok


def test_orphan_report():
    """Report for unknown task_id -> exit 1."""
    inbox = os.path.join(FAIL_DIR, "orphan-report")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=1,
        label="orphan-report",
    )
    if "orphan" not in stderr.lower():
        print(f"    WARNING: expected 'orphan' in stderr, got: {stderr[:200]}")
    return ok


def test_duplicate_report():
    """Duplicate report for same task_id -> exit 1."""
    inbox = os.path.join(FAIL_DIR, "duplicate-report")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=1,
        label="duplicate-report",
    )
    if "duplicate" not in stderr.lower():
        print(f"    WARNING: expected 'duplicate' in stderr, got: {stderr[:200]}")
    return ok


def test_unknown_status():
    """Unknown active status -> exit 1.  Uses a temp inbox so the static
    fixture tree stays schema-valid for validate-agent-inbox.py."""
    tmpdir = tempfile.mkdtemp(prefix="afc-next-test-")
    try:
        task_content = (
            "---\n"
            "schema: agent-file-coordination/task\n"
            "schema_version: 0.1.0\n"
            "task_id: task-unknown\n"
            "agent_name: Worker1\n"
            "role: implementer\n"
            "protocol_mode: task-only\n"
            "coordinator_authority: no\n"
            "status: FLYING\n"
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
            "  path: <PROJECT_ROOT>\n"
            "  may_create_worktree: no\n"
            "validation_tier: no-test-needed\n"
            "report_path: <PROJECT_ROOT>/.agent-inbox/report-Worker1-next-unknown.md\n"
            "created_at: 2026-06-11\n"
            "---\n"
            "# Task - Unknown Status\n"
        )
        with open(os.path.join(tmpdir, "task-unknown.md"), "w", encoding="utf-8") as f:
            f.write(task_content)
        ok, stdout, stderr = run(
            [tmpdir],
            expect_exit=1,
            label="unknown-status (dynamic)",
        )
        if "unknown status" not in stderr.lower():
            print(f"    WARNING: expected 'unknown status' in stderr, got: {stderr[:200]}")
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_reported_no_report():
    """REPORTED task without a report file -> exit 1 (inconsistent state)."""
    tmpdir = tempfile.mkdtemp(prefix="afc-next-test-")
    try:
        task_content = (
            "---\n"
            "schema: agent-file-coordination/task\n"
            "schema_version: 0.1.0\n"
            "task_id: task-reported-noreport\n"
            "agent_name: Worker1\n"
            "role: implementer\n"
            "protocol_mode: task-only\n"
            "coordinator_authority: no\n"
            "status: REPORTED\n"
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
            "  path: <PROJECT_ROOT>\n"
            "  may_create_worktree: no\n"
            "validation_tier: no-test-needed\n"
            "report_path: <PROJECT_ROOT>/.agent-inbox/missing-report.md\n"
            "created_at: 2026-06-11\n"
            "---\n"
            "# Task - Reported No Report\n"
        )
        with open(os.path.join(tmpdir, "task-reported.md"), "w", encoding="utf-8") as f:
            f.write(task_content)
        ok, stdout, stderr = run(
            [tmpdir],
            expect_exit=1,
            label="reported-no-report",
        )
        combined = (stdout + stderr).lower()
        if "inconsistent" not in combined and "missing report" not in combined:
            print(f"    WARNING: expected 'inconsistent' or 'missing report' in output, got: {combined[:200]}")
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_reviewing_no_report():
    """REVIEWING task without a report file -> exit 1 (inconsistent state)."""
    tmpdir = tempfile.mkdtemp(prefix="afc-next-test-")
    try:
        task_content = (
            "---\n"
            "schema: agent-file-coordination/task\n"
            "schema_version: 0.1.0\n"
            "task_id: task-reviewing-noreport\n"
            "agent_name: Worker1\n"
            "role: implementer\n"
            "protocol_mode: task-only\n"
            "coordinator_authority: no\n"
            "status: REVIEWING\n"
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
            "  path: <PROJECT_ROOT>\n"
            "  may_create_worktree: no\n"
            "validation_tier: no-test-needed\n"
            "report_path: <PROJECT_ROOT>/.agent-inbox/missing-report.md\n"
            "created_at: 2026-06-11\n"
            "---\n"
            "# Task - Reviewing No Report\n"
        )
        with open(os.path.join(tmpdir, "task-reviewing.md"), "w", encoding="utf-8") as f:
            f.write(task_content)
        ok, stdout, stderr = run(
            [tmpdir],
            expect_exit=1,
            label="reviewing-no-report",
        )
        combined = (stdout + stderr).lower()
        if "inconsistent" not in combined and "missing report" not in combined:
            print(f"    WARNING: expected 'inconsistent' or 'missing report' in output, got: {combined[:200]}")
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_missing_inbox():
    """Missing INBOX_DIR -> exit 1."""
    inbox = os.path.join(FAIL_DIR, "nonexistent-dir")
    ok, stdout, stderr = run(
        [inbox],
        expect_exit=1,
        label="missing-inbox",
    )
    if "directory not found" not in stderr.lower():
        print(f"    WARNING: expected 'directory not found' in stderr, got: {stderr[:200]}")
    return ok


def test_context_pct_handoff_preempts_review():
    """--context-pct above handoff threshold overrides RECOMMEND_REVIEW."""
    inbox = os.path.join(PASS_DIR, "report-exists")
    ok, stdout, stderr = run(
        ["--context-pct", "85", inbox],
        expect_exit=0,
        label="context-pct-handoff",
    )
    if "RECOMMEND_HANDOFF" not in stdout:
        print(f"    FAIL: expected 'RECOMMEND_HANDOFF' in stdout, got: {stdout[:300]}")
        ok = False
    if "RECOMMEND_REVIEW" in stdout:
        print(f"    FAIL: REVIEW should be preempted by handoff, got: {stdout[:300]}")
        ok = False
    return ok


def test_context_pct_handoff_no_action():
    """--context-pct above threshold recommends handoff even with no active task."""
    inbox = os.path.join(PASS_DIR, "closed-only")
    ok, stdout, stderr = run(
        ["--context-pct", "90", inbox],
        expect_exit=0,
        label="context-pct-handoff-no-action",
    )
    if "RECOMMEND_HANDOFF" not in stdout:
        print(f"    FAIL: expected 'RECOMMEND_HANDOFF' in stdout, got: {stdout[:300]}")
        ok = False
    return ok


def test_context_pct_compact_advisory():
    """--context-pct in the compact band keeps the inbox action and adds advisory."""
    inbox = os.path.join(PASS_DIR, "report-exists")
    ok, stdout, stderr = run(
        ["--context-pct", "60", inbox],
        expect_exit=0,
        label="context-pct-compact",
    )
    if "RECOMMEND_REVIEW" not in stdout:
        print(f"    FAIL: expected inbox action RECOMMEND_REVIEW retained, got: {stdout[:300]}")
        ok = False
    if "advisory:" not in stdout:
        print(f"    FAIL: expected 'advisory:' line, got: {stdout[:300]}")
        ok = False
    return ok


def test_context_pct_below_compact_no_change():
    """--context-pct below compact threshold leaves the action and adds no advisory."""
    inbox = os.path.join(PASS_DIR, "report-exists")
    ok, stdout, stderr = run(
        ["--context-pct", "40", inbox],
        expect_exit=0,
        label="context-pct-below-compact",
    )
    if "RECOMMEND_REVIEW" not in stdout:
        print(f"    FAIL: expected RECOMMEND_REVIEW, got: {stdout[:300]}")
        ok = False
    if "advisory:" in stdout:
        print(f"    FAIL: did not expect an advisory below compact threshold, got: {stdout[:300]}")
        ok = False
    return ok


def test_context_pct_json_keys():
    """--context-pct with --json exposes context_pct and advisory keys."""
    inbox = os.path.join(PASS_DIR, "report-exists")
    ok, stdout, stderr = run(
        ["--json", "--context-pct", "60", inbox],
        expect_exit=0,
        label="context-pct-json",
    )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print(f"    FAIL: stdout is not valid JSON: {stdout[:300]}")
        return False
    if data.get("context_pct") != 60:
        print(f"    FAIL: expected context_pct 60, got: {data.get('context_pct')}")
        ok = False
    if not data.get("advisory"):
        print(f"    FAIL: expected non-empty advisory, got: {data.get('advisory')}")
        ok = False
    return ok


def test_no_context_pct_backward_compatible():
    """Without --context-pct, JSON output has no context_pct/advisory keys."""
    inbox = os.path.join(PASS_DIR, "report-exists")
    ok, stdout, stderr = run(
        ["--json", inbox],
        expect_exit=0,
        label="no-context-pct-backward-compat",
    )
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        print(f"    FAIL: stdout is not valid JSON: {stdout[:300]}")
        return False
    if "context_pct" in data or "advisory" in data:
        print(f"    FAIL: unexpected context keys without --context-pct: {sorted(data.keys())}")
        ok = False
    return ok


def test_context_pct_does_not_override_fail():
    """A FAIL (inconsistent state) is never overridden by a handoff recommendation."""
    tmpdir = tempfile.mkdtemp(prefix="afc-next-test-")
    try:
        task_content = (
            "---\n"
            "schema: agent-file-coordination/task\n"
            "schema_version: 0.1.0\n"
            "task_id: task-reported-noreport\n"
            "agent_name: Worker1\n"
            "role: implementer\n"
            "protocol_mode: task-only\n"
            "coordinator_authority: no\n"
            "status: REPORTED\n"
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
            "  path: <PROJECT_ROOT>\n"
            "  may_create_worktree: no\n"
            "validation_tier: no-test-needed\n"
            "report_path: <PROJECT_ROOT>/.agent-inbox/missing-report.md\n"
            "created_at: 2026-06-11\n"
            "---\n"
            "# Task - Reported No Report\n"
        )
        with open(os.path.join(tmpdir, "task-reported.md"), "w", encoding="utf-8") as f:
            f.write(task_content)
        ok, stdout, stderr = run(
            ["--context-pct", "95", tmpdir],
            expect_exit=1,
            label="context-pct-does-not-override-fail",
        )
        if "RECOMMEND_HANDOFF" in stdout:
            print(f"    FAIL: handoff must not override a FAIL state, got: {stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_context_pct_out_of_range():
    """An out-of-range --context-pct value -> exit 1."""
    inbox = os.path.join(PASS_DIR, "report-exists")
    ok, stdout, stderr = run(
        ["--context-pct", "150", inbox],
        expect_exit=1,
        label="context-pct-out-of-range",
    )
    if "between 0 and 100" not in stderr.lower():
        print(f"    WARNING: expected range error in stderr, got: {stderr[:200]}")
    return ok


def main():
    print("Running afc-next.py fixture tests...")
    print()
    all_ok = True

    tests = [
        test_help,
        test_report_exists,
        test_report_exists_json,
        test_draft_task,
        test_assigned_no_report,
        test_running_no_report,
        test_needs_fix,
        test_closed_only,
        test_multi_active,
        test_multi_active_json,
        test_duplicate_task_id,
        test_orphan_report,
        test_duplicate_report,
        test_unknown_status,
        test_reported_no_report,
        test_reviewing_no_report,
        test_missing_inbox,
        test_context_pct_handoff_preempts_review,
        test_context_pct_handoff_no_action,
        test_context_pct_compact_advisory,
        test_context_pct_below_compact_no_change,
        test_context_pct_json_keys,
        test_no_context_pct_backward_compatible,
        test_context_pct_does_not_override_fail,
        test_context_pct_out_of_range,
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
