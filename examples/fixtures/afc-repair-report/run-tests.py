#!/usr/bin/env python3
"""Regression tests for scripts/afc-repair-report.py.

Covers the CAL-2 schema-reject repair tool: dry-run safety, enum
normalization, missing-guardrail backfill, refusal of dangerous-phrase /
empty-evidence reports, atomic --write, idempotency, and JSON output.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile


REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
SCRIPTS = os.path.join(REPO_ROOT, "scripts")
sys.path.insert(0, SCRIPTS)


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


def load_module():
    spec = importlib.util.spec_from_file_location(
        "afc_repair_report", os.path.join(SCRIPTS, "afc-repair-report.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALID_TASK = """\
---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: t1
agent_name: Worker
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

You are the assigned worker, not the coordinator.
"""


def valid_report_body():
    return (
        "\n# Worker Report\n\nDid the review.\n\nRemaining risk: none\n"
    )


def make_report(report_path, **overrides):
    """Write a report frontmatter; override any top-level/nested field.

    Overrides use dotted keys, e.g. verdict='CLOSED_GO',
    evidence_trust__trust_level='verified'. Nested maps (evidence_trust,
    guardrails, validation) are written from a base set.
    """
    verdict = overrides.pop("verdict", "GO")
    trust_level = overrides.pop("trust_level", "referenced")
    val_tier = overrides.pop("validation_tier", "no-test-needed")
    val_result = overrides.pop("validation_result", "pass")
    # guardrails is a full set unless overridden via 'guardrails_set'
    guardrails = overrides.pop(
        "guardrails_set",
        {
            "role_boundary_followed": "yes",
            "coordinator_verdict_given": "no",
            "permission_scope_expanded": "no",
            "secrets_private_data_printed": "no",
            "production_default_behavior_changed": "no",
            "commit_push_done": "no",
            "destructive_command_done": "no",
        },
    )
    evidence_refs = overrides.pop("evidence_refs", ["a.md"])
    body_text = overrides.pop("body_text", valid_report_body())

    lines = [
        "---",
        "schema: agent-file-coordination/report",
        "schema_version: 0.1.0",
        "task_id: t1",
        "agent_name: Worker",
        "verdict: {}".format(verdict),
    ]
    lines.append("evidence_refs:")
    for ref in evidence_refs:
        lines.append("  - {}".format(ref))
    lines.append("evidence_trust:")
    lines.append("  trust_level: {}".format(trust_level))
    lines.append("  untrusted_inputs_seen: no")
    lines.append("  prompt_injection_suspected: no")
    lines.append("  permission_escalation_requested: no")
    lines.append("guardrails:")
    for key in (
        "role_boundary_followed",
        "coordinator_verdict_given",
        "permission_scope_expanded",
        "secrets_private_data_printed",
        "production_default_behavior_changed",
        "commit_push_done",
        "destructive_command_done",
    ):
        if key in guardrails:
            lines.append("  {}: {}".format(key, guardrails[key]))
    lines.append("validation:")
    lines.append("  tier: {}".format(val_tier))
    lines.append("  result: {}".format(val_result))
    lines.append("reported_at: 2026-06-25")
    lines.append("---")
    lines.append(body_text)
    write(report_path, "\n".join(lines))


def test_already_valid():
    print("test_already_valid")
    mod = load_module()
    with tempfile.TemporaryDirectory(prefix="afc-repair-") as tmp:
        report = os.path.join(tmp, "report.md")
        make_report(report)
        result = mod.analyze(report)
        check("valid report analyzed as valid", result["valid"], result)
        check("valid report has no actions", result["actions"] == [], result)


def test_enum_normalization_dry_run():
    print("test_enum_normalization_dry_run")
    mod = load_module()
    with tempfile.TemporaryDirectory(prefix="afc-repair-") as tmp:
        report = os.path.join(tmp, "report.md")
        make_report(
            report,
            verdict="CLOSED_GO",
            trust_level="verified",
            validation_tier="full_suite",
            validation_result="passed",
        )
        original = open(report, encoding="utf-8").read()
        result = mod.analyze(report)
        check("bad report is not valid", not result["valid"], result)
        fields = {a["field"] for a in result["actions"]}
        check(
            "all four enum fields classified",
            {"verdict", "trust_level", "validation.tier", "validation.result"}
            <= fields,
            fields,
        )
        mapping = {a["field"]: a["new"] for a in result["actions"]}
        check("verdict CLOSED_GO -> GO", mapping.get("verdict") == "GO", mapping)
        check("trust_level verified -> referenced", mapping.get("trust_level") == "referenced", mapping)
        check("validation.tier full_suite -> full-suite", mapping.get("validation.tier") == "full-suite", mapping)
        check("validation.result passed -> pass", mapping.get("validation.result") == "pass", mapping)
        # Dry-run must not change the file.
        after = open(report, encoding="utf-8").read()
        check("dry-run leaves file unchanged", after == original, "file mutated")


def test_dry_run_does_not_write_via_cli():
    print("test_dry_run_does_not_write_via_cli")
    with tempfile.TemporaryDirectory(prefix="afc-repair-") as tmp:
        report = os.path.join(tmp, "report.md")
        make_report(report, verdict="CLOSED_GO", trust_level="verified")
        original = open(report, encoding="utf-8").read()
        proc = subprocess.run(
            [sys.executable, "-B", os.path.join(SCRIPTS, "afc-repair-report.py"), report],
            capture_output=True, text=True,
        )
        after = open(report, encoding="utf-8").read()
        check("cli dry-run exits 0", proc.returncode == 0, proc.returncode)
        check("cli dry-run prints DRY-RUN", "DRY-RUN" in proc.stdout, proc.stdout)
        check("cli dry-run leaves file unchanged", after == original, "mutated")


def test_missing_guardrails_backfilled():
    print("test_missing_guardrails_backfilled")
    mod = load_module()
    with tempfile.TemporaryDirectory(prefix="afc-repair-") as tmp:
        report = os.path.join(tmp, "report.md")
        # Report missing several guardrail keys.
        make_report(
            report,
            guardrails_set={
                "role_boundary_followed": "yes",
                "commit_push_done": "no",
            },
        )
        result = mod.analyze(report)
        add_fields = {
            a["field"] for a in result["actions"] if a["kind"] == "add-field"
        }
        check(
            "missing guardrail keys scheduled for backfill",
            {
                "guardrails.coordinator_verdict_given",
                "guardrails.permission_scope_expanded",
                "guardrails.secrets_private_data_printed",
                "guardrails.production_default_behavior_changed",
                "guardrails.destructive_command_done",
            }
            <= add_fields,
            add_fields,
        )
        # Backfilled values are all safe (no / yes for role boundary).
        for action in result["actions"]:
            if action["field"] == "guardrails.role_boundary_followed":
                continue
            check(
                "backfill value is safe (no) for {}".format(action["field"]),
                action["new"] == "no",
                action,
            )


def test_write_round_trip_validates():
    print("test_write_round_trip_validates")
    mod = load_module()
    with tempfile.TemporaryDirectory(prefix="afc-repair-") as tmp:
        task = os.path.join(tmp, "task.md")
        write(task, VALID_TASK)
        report = os.path.join(tmp, "report.md")
        make_report(
            report,
            verdict="CLOSED_GO",
            trust_level="verified",
            validation_tier="full_suite",
            validation_result="passed",
            guardrails_set={
                "role_boundary_followed": "yes",
                "commit_push_done": "no",
            },
        )
        body_before = open(report, encoding="utf-8").read().split("---\n", 2)[-1]
        proc = subprocess.run(
            [sys.executable, "-B", os.path.join(SCRIPTS, "afc-repair-report.py"),
             report, "--task", task, "--write"],
            capture_output=True, text=True,
        )
        check("--write exits 0", proc.returncode == 0, proc.returncode)
        check("--write prints REPAIRED", "REPAIRED" in proc.stdout, proc.stdout)
        # Body preserved.
        body_after = open(report, encoding="utf-8").read().split("---\n", 2)[-1]
        check("--write preserves report body", body_before == body_after, "body changed")
        # Now valid via the same validator the watcher uses.
        from afc_validation import validate_report_schema
        from afc_frontmatter import extract_structured_frontmatter
        data, body, errs = extract_structured_frontmatter(report)
        ok, reasons = validate_report_schema(data, body=body)
        check("repaired report re-validates clean", ok, reasons)


def test_dangerous_phrase_write_refused():
    print("test_dangerous_phrase_write_refused")
    with tempfile.TemporaryDirectory(prefix="afc-repair-") as tmp:
        report = os.path.join(tmp, "report.md")
        make_report(
            report,
            body_text="\n# Report\n\nThe branch was deleted.\n",
        )
        original = open(report, encoding="utf-8").read()
        proc = subprocess.run(
            [sys.executable, "-B", os.path.join(SCRIPTS, "afc-repair-report.py"),
             report, "--write"],
            capture_output=True, text=True,
        )
        after = open(report, encoding="utf-8").read()
        check(
            "dangerous-phrase --write refused (exit 2)",
            proc.returncode == 2,
            proc.returncode,
        )
        check("--write refused message printed", "--write refused" in proc.stdout, proc.stdout)
        check("dangerous-phrase report not mutated", after == original, "mutated")


def test_empty_evidence_not_auto_fixed():
    print("test_empty_evidence_not_auto_fixed")
    mod = load_module()
    with tempfile.TemporaryDirectory(prefix="afc-repair-") as tmp:
        report = os.path.join(tmp, "report.md")
        make_report(report, evidence_refs=[])
        result = mod.analyze(report)
        check("empty evidence has no auto actions", result["actions"] == [], result)
        check(
            "empty evidence flagged unfixable",
            any("evidence_refs" in r for r in result["unfixable"]),
            result["unfixable"],
        )


def test_idempotent():
    print("test_idempotent")
    with tempfile.TemporaryDirectory(prefix="afc-repair-") as tmp:
        report = os.path.join(tmp, "report.md")
        make_report(
            report,
            verdict="CLOSED_GO",
            trust_level="verified",
            validation_tier="full_suite",
            validation_result="passed",
        )
        tool = os.path.join(SCRIPTS, "afc-repair-report.py")
        # First write repairs.
        p1 = subprocess.run(
            [sys.executable, "-B", tool, report, "--write"],
            capture_output=True, text=True,
        )
        check("first repair exits 0", p1.returncode == 0, p1.returncode)
        once = open(report, encoding="utf-8").read()
        # Second run: report is now valid, ALREADY_VALID, no change.
        p2 = subprocess.run(
            [sys.executable, "-B", tool, report, "--write"],
            capture_output=True, text=True,
        )
        twice = open(report, encoding="utf-8").read()
        check("second run ALREADY_VALID", "ALREADY_VALID" in p2.stdout, p2.stdout)
        check("idempotent: file unchanged on second run", once == twice, "changed")


def test_json_output():
    print("test_json_output")
    with tempfile.TemporaryDirectory(prefix="afc-repair-") as tmp:
        report = os.path.join(tmp, "report.md")
        make_report(
            report,
            verdict="CLOSED_GO",
            trust_level="verified",
            validation_tier="full_suite",
            validation_result="passed",
        )
        tool = os.path.join(SCRIPTS, "afc-repair-report.py")
        # dry-run json
        p1 = subprocess.run(
            [sys.executable, "-B", tool, report, "--json"],
            capture_output=True, text=True,
        )
        d1 = json.loads(p1.stdout)
        check("json dry-run valid=false", d1["valid"] is False, d1)
        check("json dry-run written=false", d1["written"] is False, d1)
        check("json dry-run would_write=true", d1["would_write"] is True, d1)
        check("json actions present", len(d1["actions"]) >= 4, d1["actions"])
        # write json
        p2 = subprocess.run(
            [sys.executable, "-B", tool, report, "--json", "--write"],
            capture_output=True, text=True,
        )
        d2 = json.loads(p2.stdout)
        check("json write written=true", d2["written"] is True, d2)
        check("json write valid=true", d2["valid"] is True, d2)


def test_unknown_enum_value_left_manual():
    print("test_unknown_enum_value_left_manual")
    mod = load_module()
    with tempfile.TemporaryDirectory(prefix="afc-repair-") as tmp:
        report = os.path.join(tmp, "report.md")
        # 'totally-verified' is not in the normalization table.
        make_report(report, trust_level="totally-verified")
        result = mod.analyze(report)
        check(
            "unknown enum value not auto-fixed (no trust_level action)",
            not any(a["field"] == "trust_level" for a in result["actions"]),
            result["actions"],
        )
        check(
            "unknown enum value reported in manual",
            any("trust_level" in r for r in result["manual"]),
            result["manual"],
        )


def test_subjective_verdict_left_manual():
    """Subjective verdict words (ok/green/passed) must NOT auto-map to GO.

    Choosing GO vs PARTIAL for those is a coordinator judgment call grounded in
    the report body, not a spelling fix. Only unambiguous verdict spellings
    (closed_go/go, closed_partial/partial, closed_red/red) auto-normalize.
    """
    print("test_subjective_verdict_left_manual")
    mod = load_module()
    with tempfile.TemporaryDirectory(prefix="afc-repair-") as tmp:
        report = os.path.join(tmp, "report.md")
        make_report(report, verdict="ok")
        result = mod.analyze(report)
        check(
            "subjective verdict 'ok' not auto-fixed to GO",
            not any(a["field"] == "verdict" for a in result["actions"]),
            result["actions"],
        )
        check(
            "subjective verdict reported in manual",
            any("invalid verdict" in r for r in result["manual"]),
            result["manual"],
        )
        # Closed-status and bare verdict words still auto-fix.
        for bad, good in (("closed_go", "GO"), ("CLOSED_PARTIAL", "PARTIAL"),
                          ("closed_red", "RED")):
            make_report(report, verdict=bad)
            r = mod.analyze(report)
            action = next((a for a in r["actions"] if a["field"] == "verdict"), None)
            check(
                "verdict {} -> {}".format(bad, good),
                action is not None and action["new"] == good,
                action,
            )


def main():
    print("Running afc-repair-report fixture tests...")
    test_already_valid()
    test_enum_normalization_dry_run()
    test_dry_run_does_not_write_via_cli()
    test_missing_guardrails_backfilled()
    test_write_round_trip_validates()
    test_dangerous_phrase_write_refused()
    test_empty_evidence_not_auto_fixed()
    test_idempotent()
    test_json_output()
    test_unknown_enum_value_left_manual()
    test_subjective_verdict_left_manual()
    print("")
    if FAIL:
        print("{} check(s) failed; {} passed.".format(FAIL, PASS))
        return 1
    print("All {} afc-repair-report checks passed.".format(PASS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
