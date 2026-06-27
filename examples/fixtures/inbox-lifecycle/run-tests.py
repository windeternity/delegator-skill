#!/usr/bin/env python3
"""Test runner for inbox-lifecycle compatibility fixtures.

Exercises --active-only validation, --legacy-events compatibility,
zero-task STATUS.md generation, archive/artifact filtering, and
legacy event append-only compatibility.

Usage:
    python -B examples/fixtures/inbox-lifecycle/run-tests.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

VALIDATOR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "validate-agent-inbox.py"))
STATUS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "afc-status.py"))
AUDIT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "audit-docs.py"))

BASE = os.path.dirname(os.path.abspath(__file__))
PASS_DIR = os.path.join(BASE, "pass")
FAIL_DIR = os.path.join(BASE, "fail")

UPDATED_AT = "2026-06-12"

ROLE_BOUNDARY = (
    "\n## Role Boundary\n"
    "You are the assigned worker agent for this task, not the coordinator.\n"
    "Do not create new tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.\n"
    "If more work is needed, write it in the report as a recommendation.\n"
)


def run(script, args, expect_exit=0, label=""):
    cmd = [sys.executable, "-B", script] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    ok = result.returncode == expect_exit
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {label} (exit={result.returncode}, expected={expect_exit})")
    if not ok:
        print(f"    stdout: {result.stdout[:500]}")
        print(f"    stderr: {result.stderr[:500]}")
    return ok, result.stdout, result.stderr


# ── Positive: validate --active-only skips archive ──────────────────────

def test_active_only_skips_archive():
    """--active-only on inbox with active + archived tasks validates only active."""
    inbox = os.path.join(PASS_DIR, "active-only-skip-archive")
    ok, stdout, stderr = run(
        VALIDATOR, ["--active-only", inbox],
        expect_exit=0, label="active-only-skip-archive",
    )
    if "PASS" not in stdout:
        print(f"    FAIL: expected PASS in stdout, got: {stdout[:300]}")
        ok = False
    if "beta" in stdout:
        print(f"    FAIL: archived task beta should be skipped, got: {stdout[:300]}")
        ok = False
    return ok


def test_active_only_mixed():
    """--active-only on mixed inbox validates active and skips archive."""
    inbox = os.path.join(PASS_DIR, "mixed-active-archive")
    ok, stdout, stderr = run(
        VALIDATOR, ["--active-only", inbox],
        expect_exit=0, label="active-only-mixed",
    )
    if "gamma" not in stdout:
        print(f"    FAIL: active task gamma should appear, got: {stdout[:300]}")
        ok = False
    if "delta" in stdout:
        print(f"    FAIL: archived task delta should be skipped, got: {stdout[:300]}")
        ok = False
    return ok


def test_without_active_only_validates_all():
    """Without --active-only, archived tasks are also validated."""
    inbox = os.path.join(PASS_DIR, "active-only-skip-archive")
    ok, stdout, stderr = run(
        VALIDATOR, [inbox],
        expect_exit=0, label="no-flag-validates-all",
    )
    if "alpha" not in stdout:
        print(f"    FAIL: task alpha should appear, got: {stdout[:300]}")
        ok = False
    if "beta" not in stdout:
        print(f"    FAIL: task beta should appear, got: {stdout[:300]}")
        ok = False
    return ok


# ── Positive: --active-only skips artifacts ─────────────────────────────

def test_active_only_skips_artifacts():
    """--active-only skips artifacts/ directory (watcher JSON output)."""
    inbox = os.path.join(PASS_DIR, "artifacts-skipped")
    ok, stdout, stderr = run(
        VALIDATOR, ["--active-only", inbox],
        expect_exit=0, label="active-only-skips-artifacts",
    )
    # The watcher JSON in artifacts/ should not be validated
    if "invalid event_type" in stdout or "invalid event_type" in stderr:
        print(f"    FAIL: artifacts/ watcher JSON was validated, got: {stdout[:300]}")
        ok = False
    return ok


def test_without_active_only_artifacts_fail():
    """Without --active-only, artifacts/ watcher JSON fails strict validation."""
    inbox = os.path.join(PASS_DIR, "artifacts-skipped")
    ok, stdout, stderr = run(
        VALIDATOR, [inbox],
        expect_exit=1, label="artifacts-without-flag-fail",
    )
    # The watcher JSON lacks agent-file-coordination/event schema
    combined = (stdout + stderr).lower()
    if "event schema" not in combined and "invalid" not in combined:
        print(f"    WARNING: expected validation error for artifacts, got: {(stdout + stderr)[:300]}")
    return ok


# ── Positive: zero-task STATUS.md ───────────────────────────────────────

def test_zero_task_status_dry_run():
    """Zero-task inbox -> valid zero-row STATUS.md on dry-run."""
    inbox = os.path.join(PASS_DIR, "zero-task-inbox")
    ok, stdout, stderr = run(
        STATUS, ["--dry-run", "--updated-at", UPDATED_AT, inbox],
        expect_exit=0, label="zero-task-status-dry-run",
    )
    if "schema: agent-file-coordination/status-board" not in stdout:
        print(f"    FAIL: missing status-board schema, got: {stdout[:300]}")
        ok = False
    if "task_id" not in stdout:
        print(f"    FAIL: missing table header, got: {stdout[:300]}")
        ok = False
    return ok


def test_zero_task_status_write():
    """Zero-task inbox -> STATUS.md written and validates."""
    src = os.path.join(PASS_DIR, "zero-task-inbox")
    tmpdir = tempfile.mkdtemp(prefix="inbox-lifecycle-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        ok, stdout, stderr = run(
            STATUS, ["--updated-at", UPDATED_AT, tmpdir],
            expect_exit=0, label="zero-task-status-write",
        )
        status_path = os.path.join(tmpdir, "STATUS.md")
        if not os.path.exists(status_path):
            print("    FAIL: STATUS.md not created")
            return False
        with open(status_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "schema: agent-file-coordination/status-board" not in content:
            print(f"    FAIL: STATUS.md missing schema, got: {content[:300]}")
            ok = False
        if "| task_id |" not in content:
            print(f"    FAIL: STATUS.md missing table header, got: {content[:300]}")
            ok = False
        r = subprocess.run(
            [sys.executable, "-B", VALIDATOR, status_path],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            print(f"    FAIL: STATUS.md validation failed: {r.stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Positive: legacy events with --legacy-events ────────────────────────

def test_legacy_events_with_flag():
    """Legacy events.jsonl with historical types validates with --legacy-events."""
    inbox = os.path.join(PASS_DIR, "legacy-events-append")
    ok, stdout, stderr = run(
        VALIDATOR, ["--legacy-events", os.path.join(inbox, "events.jsonl")],
        expect_exit=0, label="legacy-events-with-flag",
    )
    return ok


def test_legacy_events_without_flag_fails():
    """Legacy events.jsonl with historical types fails strict validation."""
    inbox = os.path.join(PASS_DIR, "legacy-events-append")
    ok, stdout, stderr = run(
        VALIDATOR, [os.path.join(inbox, "events.jsonl")],
        expect_exit=1, label="legacy-events-without-flag",
    )
    if "invalid event_type" not in stdout:
        print(f"    WARNING: expected 'invalid event_type' in stdout, got: {stdout[:300]}")
    return ok


def test_legacy_events_preserved_after_status_write():
    """events.jsonl is appended to, not rewritten, after afc-status write."""
    src = os.path.join(PASS_DIR, "zero-task-inbox")
    tmpdir = tempfile.mkdtemp(prefix="inbox-lifecycle-test-")
    try:
        shutil.copytree(src, tmpdir, dirs_exist_ok=True)
        events_path = os.path.join(tmpdir, "events.jsonl")
        with open(events_path, "r", encoding="utf-8") as f:
            original = f.read()

        run(STATUS, ["--updated-at", UPDATED_AT, tmpdir], expect_exit=0, label="status-write")

        with open(events_path, "r", encoding="utf-8") as f:
            after = f.read()

        if not after.startswith(original):
            print("    FAIL: original events.jsonl content was not preserved")
            return False
        if "STATUS_UPDATED" not in after:
            print("    FAIL: STATUS_UPDATED event not appended")
            return False
        return True
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Positive: audit-docs ignores .agent-inbox ───────────────────────────

def test_audit_docs_skips_agent_inbox():
    """audit-docs.py skips .agent-inbox directories during repo scan."""
    tmpdir = tempfile.mkdtemp(prefix="inbox-lifecycle-test-")
    try:
        inbox_dir = os.path.join(tmpdir, ".agent-inbox")
        os.makedirs(inbox_dir)
        with open(os.path.join(inbox_dir, "broken.md"), "w", encoding="utf-8") as f:
            f.write("# Broken\n[missing](nonexistent.md)\n")

        with open(os.path.join(tmpdir, "README.md"), "w", encoding="utf-8") as f:
            f.write("# Project\nValid doc.\n")

        ok, stdout, stderr = run(
            AUDIT, [tmpdir],
            expect_exit=0, label="audit-docs-skips-agent-inbox",
        )
        if "PASS" not in stdout:
            print(f"    FAIL: expected PASS, got: {stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_audit_docs_single_file_still_works():
    """audit-docs.py still audits a single .agent-inbox file when targeted directly."""
    tmpdir = tempfile.mkdtemp(prefix="inbox-lifecycle-test-")
    try:
        inbox_dir = os.path.join(tmpdir, ".agent-inbox")
        os.makedirs(inbox_dir)
        broken_path = os.path.join(inbox_dir, "broken.md")
        with open(broken_path, "w", encoding="utf-8") as f:
            f.write("# Broken\n[missing](nonexistent.md)\n")

        ok, stdout, stderr = run(
            AUDIT, [broken_path],
            expect_exit=1, label="audit-docs-single-file",
        )
        if "BROKEN LINK" not in stdout:
            print(f"    FAIL: expected BROKEN LINK, got: {stdout[:300]}")
            ok = False
        return ok
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Negative: --active-only orphan report ───────────────────────────────

def test_active_only_orphan_report():
    """--active-only --cross-check: report in active area referencing archived-only task -> FAIL."""
    inbox = os.path.join(FAIL_DIR, "active-only-rejects-archive-report")
    ok, stdout, stderr = run(
        VALIDATOR, ["--active-only", "--cross-check", inbox],
        expect_exit=1, label="active-only-orphan-report",
    )
    combined = (stdout + stderr).lower()
    if "orphan" not in combined and "archived-task" not in combined:
        print(f"    WARNING: expected 'orphan' or 'archived-task' in output, got: {(stdout + stderr)[:300]}")
    return ok


def test_active_only_orphan_without_flag_passes():
    """Without --active-only, same inbox passes (task found in archive)."""
    inbox = os.path.join(FAIL_DIR, "active-only-rejects-archive-report")
    ok, stdout, stderr = run(
        VALIDATOR, ["--cross-check", inbox],
        expect_exit=0, label="orphan-without-flag-passes",
    )
    return ok


# ── Boundary: mixed inbox full validation ───────────────────────────────

def test_mixed_full_validation():
    """Full validation (no --active-only) on mixed inbox validates all files."""
    inbox = os.path.join(PASS_DIR, "mixed-active-archive")
    ok, stdout, stderr = run(
        VALIDATOR, [inbox],
        expect_exit=0, label="mixed-full-validation",
    )
    if "PASS" not in stdout:
        print(f"    FAIL: expected PASS, got: {stdout[:300]}")
        ok = False
    return ok


# ── Contradiction: archive report without archive task ──────────────────

def test_archive_report_without_task():
    """Report in active area, task only in archive. Without flag -> PASS. With --active-only -> FAIL."""
    tmpdir = tempfile.mkdtemp(prefix="inbox-lifecycle-test-")
    try:
        report_path = os.path.join(tmpdir, "report-x.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "schema: agent-file-coordination/report\n"
                "schema_version: 0.1.0\n"
                "task_id: deep-task\n"
                "agent_name: Worker\n"
                "verdict: GO\n"
                "changed_files:\n  - none\n"
                "evidence_refs:\n  - test output\n"
                "evidence_trust:\n"
                "  trust_level: reproduced\n"
                "  untrusted_inputs_seen: no\n"
                "  prompt_injection_suspected: no\n"
                "  permission_escalation_requested: no\n"
                "guardrails:\n"
                "  commit_push_done: false\n"
                "  destructive_command_done: false\n"
                "  secrets_private_data_printed: false\n"
                "  production_default_behavior_changed: false\n"
                "  role_boundary_followed: true\n"
                "  coordinator_verdict_given: false\n"
                "  permission_scope_expanded: false\n"
                "validation:\n"
                "  tier: no-test-needed\n"
                "  result: pass\n"
                "---\n\n# Report for deep task\n"
            )
        archive_dir = os.path.join(tmpdir, "archive", "2026-05")
        os.makedirs(archive_dir)
        task_path = os.path.join(archive_dir, "task-deep-task.md")
        with open(task_path, "w", encoding="utf-8") as f:
            f.write(
                "---\n"
                "schema: agent-file-coordination/task\n"
                "schema_version: 0.1.0\n"
                "task_id: deep-task\n"
                "agent_name: Worker\n"
                "role: implementer\n"
                "protocol_mode: task-only\n"
                "coordinator_authority: no\n"
                "status: CLOSED_GO\n"
                "permission_scope:\n"
                "  read_files: yes\n"
                "  write_task_files: no\n"
                "  write_reports: yes\n"
                "  modify_source: yes\n"
                "  run_commands: tests_only\n"
                "  network_access: none\n"
                "  commit_push: no\n"
                "  destructive_actions: no\n"
                "workspace:\n"
                "  mode: existing_edit_worktree\n"
                "  path: /tmp/deep\n"
                "  may_create_worktree: no\n"
                "validation_tier: targeted-test\n"
                "report_path: /tmp/deep-report.md\n"
                "created_at: 2026-05-10\n"
                "---\n\n# Deep task\n"
                + ROLE_BOUNDARY
            )

        ok1, _, _ = run(
            VALIDATOR, [tmpdir],
            expect_exit=0, label="archive-report-without-flag",
        )
        ok2, _, _ = run(
            VALIDATOR, ["--active-only", "--cross-check", tmpdir],
            expect_exit=1, label="archive-report-active-only",
        )
        return ok1 and ok2
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── Main ────────────────────────────────────────────────────────────────

def main():
    print("Running inbox-lifecycle fixture tests...")
    print()
    all_ok = True

    tests = [
        test_active_only_skips_archive,
        test_active_only_mixed,
        test_without_active_only_validates_all,
        test_active_only_skips_artifacts,
        test_without_active_only_artifacts_fail,
        test_zero_task_status_dry_run,
        test_zero_task_status_write,
        test_legacy_events_with_flag,
        test_legacy_events_without_flag_fails,
        test_legacy_events_preserved_after_status_write,
        test_audit_docs_skips_agent_inbox,
        test_audit_docs_single_file_still_works,
        test_active_only_orphan_report,
        test_active_only_orphan_without_flag_passes,
        test_mixed_full_validation,
        test_archive_report_without_task,
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
        print("All inbox-lifecycle fixture tests passed.")
        return 0
    else:
        print("Some inbox-lifecycle fixture tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
