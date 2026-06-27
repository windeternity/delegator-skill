#!/usr/bin/env python3
"""Regression tests for repair-round budget counting + warning.

Validates the acceptance criteria from brief-intake-round-warning.md:
- First NEEDS_FIX for a task: no budget warning. Second: the WARNING fires.
- --json includes the repair-round count.
- Counting reads events.jsonl and does not double-count on a re-run.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
SCRIPTS = os.path.join(REPO_ROOT, "scripts")
FIXTURE_DIR = os.path.dirname(__file__)

PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print("  [PASS] {}".format(label))
    else:
        FAIL += 1
        print("  [FAIL] {}: {}".format(label, detail))


def _load_intake():
    sys.path.insert(0, SCRIPTS)
    spec = importlib.util.spec_from_file_location(
        "afc_intake", os.path.join(SCRIPTS, "afc-intake.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _copy_fixtures(tmp_inbox):
    """Copy fixture task and report files into a temp inbox directory."""
    src_dir = os.path.join(FIXTURE_DIR, "pass", "repair-round-warning")
    for name in os.listdir(src_dir):
        src = os.path.join(src_dir, name)
        dst = os.path.join(tmp_inbox, name)
        shutil.copy2(src, dst)


def _touch_report(inbox):
    """Simulate worker submitting a new report version by touching the file.

    Changes the file's mtime so the mtime-based event_id produces a new event.
    """
    report_path = os.path.join(inbox, "report-repair-test.md")
    time.sleep(0.05)
    with open(report_path, "a", encoding="utf-8") as f:
        f.write("\n")
    time.sleep(0.05)


def test_first_needs_fix_no_warning():
    """First NEEDS_FIX: no budget warning, repair_round_count = 1."""
    intake = _load_intake()
    tmp = tempfile.mkdtemp(prefix="afc-intake-rr-")
    try:
        inbox = os.path.join(tmp, ".agent-inbox")
        os.makedirs(inbox)
        _copy_fixtures(inbox)

        result = intake.scan(inbox, set())
        tasks = result["tasks"]
        check("one task found", len(tasks) == 1, "got {}".format(len(tasks)))
        if not tasks:
            return

        task = tasks[0]
        check(
            "task is NEEDS_FIX",
            not task["ready_for_review"],
            "ready_for_review={}".format(task["ready_for_review"]),
        )
        check(
            "repair_round_count = 1",
            task.get("repair_round_count") == 1,
            "got {}".format(task.get("repair_round_count")),
        )
        has_budget_warning = any(
            "REPAIR_ROUND_BUDGET_REACHED" in w for w in task.get("warnings", [])
        )
        check(
            "no budget warning on first NEEDS_FIX",
            not has_budget_warning,
            "warnings={}".format(task.get("warnings")),
        )

        # Verify events.jsonl has exactly one REPAIR_ROUND event
        events_path = os.path.join(inbox, "events.jsonl")
        check("events.jsonl created", os.path.isfile(events_path), "missing")
        if os.path.isfile(events_path):
            with open(events_path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
            rr_events = [
                json.loads(l) for l in lines
                if json.loads(l).get("event_type") == "REPAIR_ROUND"
            ]
            check(
                "exactly one REPAIR_ROUND event",
                len(rr_events) == 1,
                "got {}".format(len(rr_events)),
            )
            if rr_events:
                check(
                    "event task_id matches",
                    rr_events[0].get("task_id") == "repair-round-test",
                    "got {}".format(rr_events[0].get("task_id")),
                )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_second_needs_fix_warning():
    """Second NEEDS_FIX (new report version): budget warning fires, count = 2."""
    intake = _load_intake()
    tmp = tempfile.mkdtemp(prefix="afc-intake-rr-")
    try:
        inbox = os.path.join(tmp, ".agent-inbox")
        os.makedirs(inbox)
        _copy_fixtures(inbox)

        # First run
        intake.scan(inbox, set())

        # Simulate worker submitting a new report version
        _touch_report(inbox)

        # Second run (new report mtime -> new event)
        result = intake.scan(inbox, set())
        tasks = result["tasks"]
        check("one task found", len(tasks) == 1, "got {}".format(len(tasks)))
        if not tasks:
            return

        task = tasks[0]
        check(
            "repair_round_count = 2",
            task.get("repair_round_count") == 2,
            "got {}".format(task.get("repair_round_count")),
        )
        has_budget_warning = any(
            "REPAIR_ROUND_BUDGET_REACHED" in w for w in task.get("warnings", [])
        )
        check(
            "budget warning fires on second NEEDS_FIX",
            has_budget_warning,
            "warnings={}".format(task.get("warnings")),
        )

        # Verify exactly two REPAIR_ROUND events (one per report version)
        events_path = os.path.join(inbox, "events.jsonl")
        with open(events_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        rr_events = [
            json.loads(l) for l in lines
            if json.loads(l).get("event_type") == "REPAIR_ROUND"
        ]
        check(
            "exactly two REPAIR_ROUND events",
            len(rr_events) == 2,
            "got {}".format(len(rr_events)),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_json_includes_repair_round_count():
    """--json output includes repair_round_count."""
    intake = _load_intake()
    tmp = tempfile.mkdtemp(prefix="afc-intake-rr-")
    try:
        inbox = os.path.join(tmp, ".agent-inbox")
        os.makedirs(inbox)
        _copy_fixtures(inbox)

        result = intake.scan(inbox, set())
        compact = intake.compact_json_result(result)
        tasks = compact.get("tasks", [])
        check("one task in JSON", len(tasks) == 1, "got {}".format(len(tasks)))
        if tasks:
            check(
                "repair_round_count in --json output",
                "repair_round_count" in tasks[0],
                "keys={}".format(sorted(tasks[0].keys())),
            )
            check(
                "repair_round_count value is 1",
                tasks[0].get("repair_round_count") == 1,
                "got {}".format(tasks[0].get("repair_round_count")),
            )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_no_double_count_on_rerun():
    """Re-running intake over unchanged state does NOT double-count events."""
    intake = _load_intake()
    tmp = tempfile.mkdtemp(prefix="afc-intake-rr-")
    try:
        inbox = os.path.join(tmp, ".agent-inbox")
        os.makedirs(inbox)
        _copy_fixtures(inbox)

        # Run 3 times without touching the report
        for _ in range(3):
            intake.scan(inbox, set())

        events_path = os.path.join(inbox, "events.jsonl")
        with open(events_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        rr_events = [
            json.loads(l) for l in lines
            if json.loads(l).get("event_type") == "REPAIR_ROUND"
        ]
        check(
            "exactly one REPAIR_ROUND after 3 runs (no double-count)",
            len(rr_events) == 1,
            "got {}".format(len(rr_events)),
        )

        # Final run should still report count correctly
        result = intake.scan(inbox, set())
        task = result["tasks"][0] if result["tasks"] else {}
        check(
            "repair_round_count correct after 3 runs",
            task.get("repair_round_count") == 1,
            "got {}".format(task.get("repair_round_count")),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_ready_task_has_zero_count():
    """A READY task should have repair_round_count = 0."""
    intake = _load_intake()
    tmp = tempfile.mkdtemp(prefix="afc-intake-rr-")
    try:
        inbox = os.path.join(tmp, ".agent-inbox")
        workspace = os.path.join(tmp, "workspace")
        os.makedirs(inbox)
        os.makedirs(workspace)
        # Initialize a clean git repo so the workspace passes git checks.
        # Use subprocess.DEVNULL (not ">nul") so POSIX shells do not create a
        # literal file named "nul" in the checkout and dirty the worktree.
        _quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        subprocess.run(["git", "init", workspace], check=False, **_quiet)
        subprocess.run(["git", "-C", workspace, "config", "user.email", "test@test"], check=False, **_quiet)
        subprocess.run(["git", "-C", workspace, "config", "user.name", "Test"], check=False, **_quiet)
        # Create a task that will be READY (valid workspace, no issues)
        task_content = """---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: ready-test
agent_name: TestWorker
role: implementer
protocol_mode: task-only
coordinator_authority: no
routing_decision: DIRECT
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: yes
  run_commands: none
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: existing_edit_worktree
  path: WORKSPACE_PATH
  may_create_worktree: no
  locked_files_or_areas: scripts/
completion_marker: done
validation_tier: no-test-needed
report_path: INBOX_PATH/report-ready-test.md
created_at: "2026-06-24"
---

## Role Boundary

Worker only: no reassign, scope expansion, or final verdict.

# Ready Task
""".replace("WORKSPACE_PATH", workspace.replace("\\", "/")).replace("INBOX_PATH", inbox.replace("\\", "/"))

        report_content = """---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: ready-test
agent_name: TestWorker
verdict: GO
changed_files:
  - none
evidence_refs:
  - test-evidence
evidence_trust:
  trust_level: referenced
  untrusted_inputs_seen: no
  prompt_injection_suspected: no
  permission_escalation_requested: no
guardrails:
  role_boundary_followed: yes
  coordinator_verdict_given: no
  permission_scope_expanded: no
  secrets_private_data_printed: no
  production_default_behavior_changed: no
  commit_push_done: no
  destructive_command_done: no
validation:
  tier: no-test-needed
  result: pass
reported_at: "2026-06-24"
---

# Ready Report
"""

        with open(os.path.join(inbox, "task-ready-test.md"), "w", encoding="utf-8") as f:
            f.write(task_content)
        with open(os.path.join(inbox, "report-ready-test.md"), "w", encoding="utf-8") as f:
            f.write(report_content)

        result = intake.scan(inbox, set())
        tasks = result["tasks"]
        check("one task found", len(tasks) == 1, "got {}".format(len(tasks)))
        if tasks:
            task = tasks[0]
            check(
                "task is READY",
                task["ready_for_review"],
                "ready_for_review={}".format(task["ready_for_review"]),
            )
            check(
                "READY task has repair_round_count = 0",
                task.get("repair_round_count") == 0,
                "got {}".format(task.get("repair_round_count")),
            )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_missing_report_does_not_consume_round():
    """A REPORT_MISSING intake (no report file) must not append a REPAIR_ROUND
    marker or consume a repair-round slot; otherwise the first real NEEDS_FIX
    later reaches MAX_EXPECTED_ROUNDS one round early."""
    intake = _load_intake()
    tmp = tempfile.mkdtemp(prefix="afc-intake-missing-")
    try:
        inbox = os.path.join(tmp, ".agent-inbox")
        workspace = os.path.join(tmp, "workspace")
        os.makedirs(inbox)
        os.makedirs(workspace)
        _quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        subprocess.run(["git", "init", workspace], check=False, **_quiet)
        subprocess.run(["git", "-C", workspace, "config", "user.email", "test@test"], check=False, **_quiet)
        subprocess.run(["git", "-C", workspace, "config", "user.name", "Test"], check=False, **_quiet)
        # Task with a report_path that does NOT exist on disk -> REPORT_MISSING.
        task_content = """---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: missing-report-test
agent_name: TestWorker
role: implementer
protocol_mode: task-only
coordinator_authority: no
routing_decision: DIRECT
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: yes
  run_commands: none
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: existing_edit_worktree
  path: WORKSPACE_PATH
  may_create_worktree: no
  locked_files_or_areas: scripts/
completion_marker: done
validation_tier: no-test-needed
report_path: INBOX_PATH/report-missing-report-test.md
created_at: "2026-06-24"
---

## Role Boundary

Worker only: no reassign, scope expansion, or final verdict.
""".replace("WORKSPACE_PATH", workspace.replace("\\", "/")).replace("INBOX_PATH", inbox.replace("\\", "/"))

        with open(os.path.join(inbox, "task-missing-report-test.md"), "w", encoding="utf-8") as f:
            f.write(task_content)
        # Deliberately do NOT create the report file.

        # First missing-report intake.
        result = intake.scan(inbox, set())
        task = result["tasks"][0] if result["tasks"] else {}
        check(
            "missing-report task is not ready",
            not task.get("ready_for_review"),
            "ready_for_review={}".format(task.get("ready_for_review")),
        )
        check(
            "missing-report does not consume a repair round",
            task.get("repair_round_count") == 0,
            "got {}".format(task.get("repair_round_count")),
        )
        events_path = os.path.join(inbox, "events.jsonl")
        rr_events = []
        if os.path.isfile(events_path):
            with open(events_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("event_type") == "REPAIR_ROUND":
                        rr_events.append(ev)
        check(
            "no REPAIR_ROUND event appended for missing report",
            len(rr_events) == 0,
            "got {}".format(len(rr_events)),
        )

        # A second missing-report intake must still not consume a slot.
        result = intake.scan(inbox, set())
        task = result["tasks"][0] if result["tasks"] else {}
        check(
            "second missing-report still zero rounds",
            task.get("repair_round_count") == 0,
            "got {}".format(task.get("repair_round_count")),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    print("Running repair-round budget warning regression tests...")
    print()
    test_first_needs_fix_no_warning()
    print()
    test_second_needs_fix_warning()
    print()
    test_json_includes_repair_round_count()
    print()
    test_no_double_count_on_rerun()
    print()
    test_ready_task_has_zero_count()
    print()
    test_missing_report_does_not_consume_round()
    print()
    print("Results: {} passed, {} failed".format(PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
