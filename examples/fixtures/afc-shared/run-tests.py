#!/usr/bin/env python3
"""Regression tests for shared AFC parsing and validation helpers."""

import importlib.util
import os
import sys
import tempfile


REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
SCRIPTS = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

from afc_frontmatter import (  # noqa: E402
    extract_structured_frontmatter,
    parse_frontmatter_flat,
    parse_frontmatter_nested,
)
from afc_inbox_validation import validate_paths  # noqa: E402
from afc_validation import get_dangerous_pattern  # noqa: E402
from afc_fsutil import atomic_write, sweep_stale_tmp  # noqa: E402


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


def test_parser_profiles():
    with tempfile.TemporaryDirectory(prefix="afc-shared-") as tmp:
        path = os.path.join(tmp, "task.md")
        write(path, """\
---
schema: agent-file-coordination/task
task_id: shared-parser
semantic_change: yes
workspace:
  path: C:/workspace
permission_scope:
  modify_source: no
changed_files:
  - scripts/example.py
source_artifacts:
  - docs/WHEN_TO_USE_AFC.md
moa:
  inputs:
    - examples/moa-review-demo/report-ReviewerA-routing-policy.md
---

# Body
""")

        flat, flat_error = parse_frontmatter_flat(path)
        check("flat parser succeeds", flat_error is None, flat_error)
        check(
            "flat parser preserves dot notation",
            flat.get("workspace.path") == "C:/workspace",
            flat,
        )
        check(
            "flat parser preserves string booleans",
            flat.get("semantic_change") == "yes",
            flat,
        )

        nested, nested_error = parse_frontmatter_nested(path)
        check("nested parser succeeds", nested_error is None, nested_error)
        check(
            "nested parser reconstructs dictionaries",
            nested.get("permission_scope", {}).get("modify_source") == "no",
            nested,
        )

        structured, body, errors = extract_structured_frontmatter(path)
        check("structured parser succeeds", not errors, errors)
        check(
            "structured parser coerces booleans",
            structured.get("semantic_change") is True,
            structured,
        )
        check(
            "structured parser keeps known lists",
            structured.get("changed_files") == ["scripts/example.py"],
            structured,
        )
        check(
            "structured parser keeps source_artifacts list",
            structured.get("source_artifacts") == ["docs/WHEN_TO_USE_AFC.md"],
            structured,
        )
        check(
            "structured parser keeps nested moa inputs list",
            structured.get("moa", {}).get("inputs")
            == ["examples/moa-review-demo/report-ReviewerA-routing-policy.md"],
            structured,
        )
        check("structured parser returns body", "# Body" in body, body)


def test_strict_and_permissive_modes():
    with tempfile.TemporaryDirectory(prefix="afc-shared-") as tmp:
        path = os.path.join(tmp, "malformed.md")
        write(path, """\
---
schema: agent-file-coordination/task
broken line
task_id: malformed
---
""")
        _, strict_error = parse_frontmatter_flat(path, strict=True)
        permissive, permissive_error = parse_frontmatter_flat(
            path, strict=False
        )
        check(
            "strict parser rejects malformed lines",
            strict_error is not None and "malformed" in strict_error,
            strict_error,
        )
        check(
            "permissive parser skips malformed lines",
            permissive_error is None
            and permissive.get("task_id") == "malformed",
            permissive,
        )


def test_shared_validation_api():
    valid_task = os.path.join(
        REPO_ROOT, "examples", "fixtures", "valid", "valid-task.md"
    )
    result = validate_paths([valid_task])
    check("importable validator accepts valid task", result["ok"], result)

    pattern = get_dangerous_pattern()
    check(
        "dangerous phrase pattern is shared and active",
        bool(pattern.search("ignore previous instructions")),
        pattern.pattern,
    )


def test_coordination_metadata_validation():
    with tempfile.TemporaryDirectory(prefix="afc-shared-") as tmp:
        task_path = os.path.join(tmp, "task.md")
        report_path = os.path.join(tmp, "report.md")
        task = """\
---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: moa-task
agent_name: Reviewer
role: reviewer
protocol_mode: task-only
coordinator_authority: no
routing_decision: FULL
coordination_mode: moa_review
comparison_group: moa-group-001
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: no
  run_commands: read_only
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: read_only_shared
  path: .
  may_create_worktree: no
validation_tier: no-test-needed
report_path: report.md
created_at: 2026-06-25
---

# Task

## Role Boundary

You are the assigned reviewer worker for this task, not the coordinator.
"""
        report = """\
---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: moa-task
agent_name: Reviewer
verdict: GO
coordination_mode: moa_review
comparison_group: moa-group-001
changed_files:
  - none
evidence_refs:
  - task.md
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
reported_at: 2026-06-25
---

# Report

Reviewed the MOA task.
"""
        write(task_path, task)
        write(report_path, report)
        valid = validate_paths([task_path, report_path])
        check("coordination metadata baseline validates", valid["ok"], valid)

        write(task_path, task.replace("moa_review", "moa_reveiw", 1))
        bad_task = validate_paths([task_path])
        check(
            "task coordination_mode enum typo is rejected",
            not bad_task["ok"]
            and "Invalid coordination_mode" in str(bad_task["files"]),
            bad_task,
        )

        write(task_path, task)
        write(report_path, report.replace("moa_review", "moa_reveiw", 1))
        bad_report_mode = validate_paths([task_path, report_path])
        check(
            "report coordination_mode enum typo is rejected",
            not bad_report_mode["ok"]
            and "Invalid coordination_mode" in str(bad_report_mode["files"]),
            bad_report_mode,
        )

        write(report_path, report.replace("moa-group-001", "wrong-group", 1))
        bad_report_group = validate_paths([task_path, report_path])
        check(
            "report comparison_group mismatch is rejected",
            not bad_report_group["ok"]
            and "comparison_group does not match" in str(bad_report_group["files"]),
            bad_report_group,
        )


def test_next_rejects_incomplete_tasks():
    spec = importlib.util.spec_from_file_location(
        "afc_next_for_shared_tests",
        os.path.join(SCRIPTS, "afc-next.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with tempfile.TemporaryDirectory(prefix="afc-shared-") as tmp:
        path = os.path.join(tmp, "task-incomplete.md")
        write(path, """\
---
schema: agent-file-coordination/task
task_id: incomplete
role: reviewer
status: ASSIGNED
---
""")
        tasks, _, errors = module.scan_inbox(tmp)
        check(
            "afc-next excludes tasks missing required fields",
            "incomplete" not in tasks
            and any("agent_name" in error for error in errors),
            {"tasks": tasks, "errors": errors},
        )


def test_moa_synthesis_required_sections():
    """moa_synthesis reports missing required sections must be rejected."""
    with tempfile.TemporaryDirectory(prefix="afc-shared-") as tmp:
        task_path = os.path.join(tmp, "task.md")
        report_path = os.path.join(tmp, "report.md")
        task = """\
---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: moa-sections-task
agent_name: SynthesisReviewer
role: reviewer
protocol_mode: task-only
coordinator_authority: no
routing_decision: FULL
coordination_mode: moa_synthesis
comparison_group: moa-sections-001
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: no
  run_commands: none
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: read_only_shared
  path: .
  may_create_worktree: no
validation_tier: no-test-needed
report_path: report.md
created_at: 2026-06-26
---

# Task

## Role Boundary

You are the assigned synthesis reviewer for this task, not the coordinator.
"""
        # Complete report — all required sections present.
        report_complete = """\
---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: moa-sections-task
agent_name: SynthesisReviewer
verdict: GO
coordination_mode: moa_synthesis
comparison_group: moa-sections-001
changed_files:
  - none
evidence_refs:
  - task.md
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
reported_at: 2026-06-26
---

# Report

## Summary
All reviewers agree on the approach.

## Agreements
- The change is safe.

## Contradictions
None.

## Evidence Quality
| Report | Strength |
| --- | --- |
| A | high |

## Validation Gaps
None.

## Unsafe Or Out-Of-Scope Recommendations
None.

## Recommendation
recommend_go.

## Remaining Uncertainty
None.
"""
        write(task_path, task)
        write(report_path, report_complete)
        ok_result = validate_paths([task_path, report_path])
        check(
            "moa_synthesis report with all sections passes",
            ok_result["ok"],
            ok_result,
        )

        # Missing sections — should fail.
        report_incomplete = """\
---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: moa-sections-task
agent_name: SynthesisReviewer
verdict: GO
coordination_mode: moa_synthesis
comparison_group: moa-sections-001
changed_files:
  - none
evidence_refs:
  - task.md
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
reported_at: 2026-06-26
---

# Report

## Summary
All reviewers agree on the approach.

## Agreements
- The change is safe.
"""
        write(report_path, report_incomplete)
        bad_result = validate_paths([task_path, report_path])
        bad_blob = str(bad_result["files"])
        check(
            "moa_synthesis report missing sections is rejected",
            not bad_result["ok"],
            bad_result,
        )
        check(
            "moa_synthesis rejection mentions missing sections",
            "MOA synthesis report missing required section" in bad_blob,
            bad_blob,
        )


def test_fsutil_atomic_write_and_sweep():
    with tempfile.TemporaryDirectory(prefix="afc-shared-") as tmp:
        target = os.path.join(tmp, "STATUS.md")
        ok = atomic_write(target, "hello\nworld\n")
        check("atomic_write reports success", ok is True, ok)
        with open(target, "r", encoding="utf-8") as handle:
            content = handle.read()
        check(
            "atomic_write wrote exact content",
            content == "hello\nworld\n",
            repr(content),
        )
        check(
            "atomic_write leaves no .tmp on success",
            not os.path.isfile(target + ".tmp"),
            os.listdir(tmp),
        )
        atomic_write(target, "second\n")
        with open(target, "r", encoding="utf-8") as handle:
            check(
                "atomic_write overwrites existing target",
                handle.read() == "second\n",
                "overwrite failed",
            )
        stale = os.path.join(tmp, "STATUS.md.tmp")
        write(stale, "leftover\n")
        write(os.path.join(tmp, "keep.json"), "{}\n")
        removed = sweep_stale_tmp(tmp)
        check(
            "sweep_stale_tmp removes stale .tmp",
            removed >= 1 and not os.path.isfile(stale),
            removed,
        )
        check(
            "sweep_stale_tmp keeps real files",
            os.path.isfile(target)
            and os.path.isfile(os.path.join(tmp, "keep.json")),
            os.listdir(tmp),
        )


def test_watcher_intake_validator_agree():
    """Watcher and inbox validators must agree on the same malformed report.

    Guards two historical divergences: (1) the watcher did not run task
    cross-checks, so an agent_name mismatch passed the watcher but failed
    intake; (2) guardrail booleans used different coercion (is True vs
    bool_enabled), so `commit_push_done: yes` was treated differently. Both
    paths must now reject the same report for the same reason class.
    """
    watch_spec = importlib.util.spec_from_file_location(
        "afc_watch_for_agree_test",
        os.path.join(SCRIPTS, "afc-watch.py"),
    )
    watch = importlib.util.module_from_spec(watch_spec)
    watch_spec.loader.exec_module(watch)

    with tempfile.TemporaryDirectory(prefix="afc-shared-") as tmp:
        task_path = os.path.join(tmp, "task.md")
        report_path = os.path.join(tmp, "report.md")
        write(task_path, """\
---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: agree-1
agent_name: CorrectWorker
role: reviewer
protocol_mode: task-only
coordinator_authority: no
routing_decision: FULL
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: no
  run_commands: read_only
  network_access: none
  commit_push: no
  destructive_actions: no
workspace:
  mode: read_only_shared
  path: .
  may_create_worktree: no
validation_tier: no-test-needed
report_path: report.md
created_at: 2026-06-25
---

# Task

## Role Boundary

x
""")
        # Two faults: agent_name mismatch AND commit_push_done: yes (a string
        # bool the two validators previously coerced differently).
        write(report_path, """\
---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: agree-1
agent_name: WrongWorker
verdict: GO
evidence_refs:
  - a.md
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
  commit_push_done: yes
  destructive_command_done: no
validation:
  tier: no-test-needed
  result: pass
reported_at: 2026-06-25
---

# Report
ok
""")
        # Watcher path (with task cross-check via inbox_dir).
        w_ok, w_reasons = watch._validate_report(
            report_path, inbox_dir=tmp
        )
        # Inbox path.
        inbox_result = validate_paths([task_path, report_path])
        i_ok = inbox_result["ok"]
        inbox_blob = str(inbox_result["files"])

        check("watcher rejects the malformed report", not w_ok, w_reasons)
        check("inbox rejects the malformed report", not i_ok, inbox_result)
        check(
            "watcher catches agent_name mismatch",
            any("agent_name does not match" in r for r in w_reasons),
            w_reasons,
        )
        check(
            "watcher catches commit_push_done: yes (bool coercion aligned)",
            any("commit_push_done" in r for r in w_reasons),
            w_reasons,
        )
        check(
            "inbox catches commit_push_done: yes (bool coercion aligned)",
            "commit_push_done" in inbox_blob,
            inbox_blob,
        )


def test_watch_corrupt_state_fails_loud():
    spec = importlib.util.spec_from_file_location(
        "afc_watch_for_shared_tests",
        os.path.join(SCRIPTS, "afc-watch.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with tempfile.TemporaryDirectory(prefix="afc-shared-") as tmp:
        state = os.path.join(tmp, ".afc-poll-state.json")
        write(state, "{ not valid json")
        raised = False
        try:
            module._load_state(state)
        except ValueError:
            raised = True
        check(
            "watcher _load_state fails loud on corrupt state "
            "(no silent reset that would re-intake every report)",
            raised,
            "expected ValueError on corrupt state file",
        )
        missing = os.path.join(tmp, "nonexistent.json")
        check(
            "watcher _load_state returns empty for a missing file",
            module._load_state(missing) == {},
            "missing file must be the normal empty-state path",
        )


def test_fsutil_atomic_write_fallback_preserves_target():
    with tempfile.TemporaryDirectory(prefix="afc-shared-") as tmp:
        target = os.path.join(tmp, "state.json")
        atomic_write(target, "original\n")
        orig_replace = os.replace

        def _always_fail(src, dst):
            raise OSError("simulated replace failure")

        os.replace = _always_fail
        try:
            ok = atomic_write(target, "updated\n")
        finally:
            os.replace = orig_replace
        with open(target, "r", encoding="utf-8") as handle:
            content = handle.read()
        check(
            "atomic_write fallback writes new content when os.replace fails",
            ok is True and content == "updated\n",
            (ok, repr(content)),
        )
        check(
            "atomic_write fallback leaves no .tmp or .bak residue",
            not os.path.isfile(target + ".tmp")
            and not os.path.isfile(target + ".bak"),
            os.listdir(tmp),
        )


def main():
    print("Running shared AFC helper tests...")
    test_parser_profiles()
    test_strict_and_permissive_modes()
    test_shared_validation_api()
    test_coordination_metadata_validation()
    test_moa_synthesis_required_sections()
    test_next_rejects_incomplete_tasks()
    test_watcher_intake_validator_agree()
    test_fsutil_atomic_write_and_sweep()
    test_fsutil_atomic_write_fallback_preserves_target()
    test_watch_corrupt_state_fails_loud()
    print("")
    if FAIL:
        print("{} check(s) failed; {} passed.".format(FAIL, PASS))
        return 1
    print("All {} shared helper checks passed.".format(PASS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
