#!/usr/bin/env python3
"""Fixture tests for the minimal Coordinator-Worker-Report-Validate-NextAction loop."""

import os
import sys
import tempfile

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
SCRIPTS = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

from afc_inbox_validation import validate_paths  # noqa: E402
from afc_frontmatter import extract_structured_frontmatter  # noqa: E402

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


def write(path, content):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


TASK_VALID = """\
---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: loop-test-valid
agent_name: Worker
role: implementer
protocol_mode: task-only
coordinator_authority: no
routing_decision: FULL
coordination_mode: delegate_full
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: yes
  run_commands: tests_only
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: existing_edit_worktree
  path: .
  may_create_worktree: no
validation_tier: targeted-test
report_path: report.md
created_at: 2026-06-26
---

# Task

## Role Boundary

You are the assigned worker agent for this task, not the coordinator.
"""

REPORT_VALID = """\
---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: loop-test-valid
agent_name: Worker
verdict: GO
coordination_mode: delegate_full
changed_files:
  - sample.py
evidence_refs:
  - sample.py
evidence_trust:
  trust_level: self_claim
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
  tier: targeted-test
  result: pass
reported_at: 2026-06-26
---

# Report

## Summary

Fixed typo in sample.py.
"""

REPORT_MISSING_VERDICT = """\
---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: loop-test-valid
agent_name: Worker
coordination_mode: delegate_full
changed_files:
  - sample.py
evidence_refs:
  - sample.py
evidence_trust:
  trust_level: self_claim
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
  tier: targeted-test
  result: pass
reported_at: 2026-06-26
---

# Report

## Summary

Fixed typo in sample.py.
"""

REPORT_PERMISSION_VIOLATION = """\
---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: loop-test-valid
agent_name: Worker
verdict: GO
coordination_mode: delegate_full
changed_files:
  - sample.py
  - secret.env
evidence_refs:
  - sample.py
evidence_trust:
  trust_level: self_claim
  untrusted_inputs_seen: no
  prompt_injection_suspected: no
  permission_escalation_requested: no
guardrails:
  role_boundary_followed: no
  coordinator_verdict_given: no
  permission_scope_expanded: yes
  secrets_private_data_printed: no
  production_default_behavior_changed: no
  commit_push_done: no
  destructive_command_done: no
validation:
  tier: targeted-test
  result: pass
reported_at: 2026-06-26
---

# Report

## Summary

Fixed typo and also modified secret.env.
"""


def test_valid_loop_passes():
    """Valid task+report pair should pass validation."""
    with tempfile.TemporaryDirectory(prefix="afc-loop-") as tmp:
        task_path = os.path.join(tmp, "task-Worker-test.md")
        report_path = os.path.join(tmp, "report-Worker-test.md")
        write(task_path, TASK_VALID)
        write(report_path, REPORT_VALID)
        result = validate_paths([task_path, report_path])
        check(
            "valid loop task+report passes",
            result["ok"],
            result,
        )


def test_missing_verdict_rejected():
    """Report missing verdict field should be rejected."""
    with tempfile.TemporaryDirectory(prefix="afc-loop-") as tmp:
        task_path = os.path.join(tmp, "task-Worker-test.md")
        report_path = os.path.join(tmp, "report-Worker-test.md")
        write(task_path, TASK_VALID)
        write(report_path, REPORT_MISSING_VERDICT)
        result = validate_paths([task_path, report_path])
        blob = str(result.get("files", ""))
        check(
            "report missing verdict is rejected",
            not result["ok"],
            result,
        )
        check(
            "rejection mentions verdict",
            "verdict" in blob.lower(),
            blob,
        )


def test_permission_violation_rejected():
    """Report with permission_scope_expanded should be flagged."""
    with tempfile.TemporaryDirectory(prefix="afc-loop-") as tmp:
        task_path = os.path.join(tmp, "task-Worker-test.md")
        report_path = os.path.join(tmp, "report-Worker-test.md")
        write(task_path, TASK_VALID)
        write(report_path, REPORT_PERMISSION_VIOLATION)
        result = validate_paths([task_path, report_path])
        blob = str(result.get("files", ""))
        check(
            "permission violation report is rejected",
            not result["ok"],
            result,
        )
        check(
            "rejection mentions permission or guardrail",
            "permission" in blob.lower() or "guardrail" in blob.lower() or "expanded" in blob.lower(),
            blob,
        )


def test_demo_files_validate():
    """The actual minimal-loop-demo files should pass validation."""
    demo_dir = os.path.join(REPO_ROOT, "examples", "minimal-loop-demo")
    task_path = os.path.join(demo_dir, "task-Worker-fix-typo.md")
    report_path = os.path.join(demo_dir, "report-Worker-fix-typo.md")
    if not os.path.exists(task_path) or not os.path.exists(report_path):
        check("demo files exist", False, f"missing: {task_path} or {report_path}")
        return
    result = validate_paths([task_path, report_path])
    check(
        "minimal-loop-demo files validate",
        result["ok"],
        result,
    )


def test_demo_report_path_matches_basename():
    """Demo task report_path should match the actual report file basename."""
    demo_dir = os.path.join(REPO_ROOT, "examples", "minimal-loop-demo")
    task_path = os.path.join(demo_dir, "task-Worker-fix-typo.md")
    report_path = os.path.join(demo_dir, "report-Worker-fix-typo.md")
    if not os.path.exists(task_path):
        check("demo task exists", False, f"missing: {task_path}")
        return
    data, _body, _errs = extract_structured_frontmatter(task_path)
    declared = data.get("report_path", "") if data else ""
    actual_basename = os.path.basename(report_path)
    check(
        "demo task report_path matches report basename",
        declared == actual_basename,
        f"declared={declared!r}, expected={actual_basename!r}",
    )


def main():
    print("Running afc-loop fixture tests...")
    print()
    for test_fn in [
        test_valid_loop_passes,
        test_missing_verdict_rejected,
        test_permission_violation_rejected,
        test_demo_files_validate,
        test_demo_report_path_matches_basename,
    ]:
        try:
            test_fn()
        except Exception as exc:
            print("  [FAIL] {}: {}".format(test_fn.__name__, exc))
            global FAIL
            FAIL += 1
        print()
    print("{} passed, {} failed.".format(PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
