#!/usr/bin/env python3
"""Generate a compact, schema-valid worker report from a task file."""

import argparse
import os
import re
import sys
import tempfile
from datetime import date

from afc_validation import (
    TRUST_LEVELS,
    VALIDATION_RESULTS,
    VALIDATION_TIERS,
    VERDICTS,
    validate_report_schema,
)
from afc_frontmatter import parse_frontmatter_nested


REPORT_BUDGET_BYTES = 3 * 1024

# Placeholder text the worker must replace before a report is accepted.
TODO_RE = re.compile(r'\bTODO\b', re.IGNORECASE)


def parse_task(path):
    return parse_frontmatter_nested(path, strict=False)


def yaml_list(lines, key, values):
    lines.append("{}:".format(key))
    for value in values:
        lines.append("  - {}".format(value))


def resolve_output_path(task_path, output):
    if os.path.isabs(output):
        return os.path.abspath(output)
    task_dir = os.path.dirname(task_path)
    normalized = output.replace("\\", "/")
    if (
        os.path.basename(task_dir) == ".agent-inbox"
        and normalized.startswith(".agent-inbox/")
    ):
        return os.path.abspath(os.path.join(os.path.dirname(task_dir), output))
    return os.path.abspath(os.path.join(task_dir, output))


def path_is_within(path, parent):
    try:
        path = os.path.abspath(path)
        parent = os.path.abspath(parent)
        return os.path.commonpath(
            [os.path.normcase(path), os.path.normcase(parent)]
        ) == os.path.normcase(parent)
    except ValueError:
        return False


def build_report(task, args):
    changed = args.changed_file or ["none"]
    evidence = args.evidence_ref
    coordination_mode = str(task.get("coordination_mode") or "").strip()
    comparison_group = str(task.get("comparison_group") or "").strip()
    report = {
        "task_id": task["task_id"],
        "agent_name": task["agent_name"],
        "verdict": args.verdict,
        "changed_files": changed,
        "evidence_refs": evidence,
        "evidence_trust": {
            "trust_level": args.trust_level,
            "untrusted_inputs_seen": False,
            "prompt_injection_suspected": False,
            "permission_escalation_requested": False,
        },
        "guardrails": {
            "role_boundary_followed": True,
            "coordinator_verdict_given": False,
            "permission_scope_expanded": False,
            "secrets_private_data_printed": False,
            "production_default_behavior_changed": False,
            "commit_push_done": False,
            "destructive_command_done": False,
        },
        "validation": {
            "tier": args.validation_tier,
            "result": args.validation_result,
        },
    }
    if coordination_mode:
        report["coordination_mode"] = coordination_mode
    if comparison_group:
        report["comparison_group"] = comparison_group
    report_body = "{}\nRemaining risk: {}".format(
        args.summary,
        args.remaining_risk,
    )
    valid, reasons = validate_report_schema(report, report_body, task)
    if not valid:
        return None, reasons

    lines = [
        "---",
        "schema: agent-file-coordination/report",
        "schema_version: 0.1.0",
        "task_id: {}".format(task["task_id"]),
        "agent_name: {}".format(task["agent_name"]),
        "verdict: {}".format(args.verdict),
    ]
    if coordination_mode:
        lines.append("coordination_mode: {}".format(coordination_mode))
    if comparison_group:
        lines.append("comparison_group: {}".format(comparison_group))
    yaml_list(lines, "changed_files", changed)
    yaml_list(lines, "evidence_refs", evidence)
    lines.extend([
        "evidence_trust:",
        "  trust_level: {}".format(args.trust_level),
        "  untrusted_inputs_seen: no",
        "  prompt_injection_suspected: no",
        "  permission_escalation_requested: no",
        "guardrails:",
        "  role_boundary_followed: yes",
        "  coordinator_verdict_given: no",
        "  permission_scope_expanded: no",
        "  secrets_private_data_printed: no",
        "  production_default_behavior_changed: no",
        "  commit_push_done: no",
        "  destructive_command_done: no",
        "validation:",
        "  tier: {}".format(args.validation_tier),
        "  result: {}".format(args.validation_result),
        "reported_at: {}".format(args.reported_at),
        "---",
        "",
        "# Worker Report",
        "",
        args.summary.strip(),
        "",
        "Remaining risk: {}".format(args.remaining_risk.strip() or "none"),
        "",
    ])
    return "\n".join(lines), []


def check_report(task_path):
    """Self-check: validate the already-written report against its task.

    Runs the exact same cross-file validation the coordinator's intake/CAL-2
    watcher uses, so a worker who sees PASS here will not be rejected later.
    """
    task, error = parse_task(task_path)
    if error:
        print("CHECK: FAIL - cannot read task: {}".format(error), file=sys.stderr)
        return 1
    if task.get("schema") != "agent-file-coordination/task":
        print("CHECK: FAIL - --task is not an AFC task file", file=sys.stderr)
        return 1
    declared = task.get("report_path")
    if not declared:
        print("CHECK: FAIL - task has no report_path", file=sys.stderr)
        return 1
    report_path = resolve_output_path(task_path, declared)
    if not os.path.isfile(report_path):
        print(
            "CHECK: FAIL - report not found at {}".format(report_path),
            file=sys.stderr,
        )
        print(
            "  fix: write it with afc-report.py (do not hand-write the report).",
            file=sys.stderr,
        )
        return 1
    try:
        from afc_inbox_validation import (
            format_validation_result,
            validate_paths,
        )
    except ImportError as exc:
        print("CHECK: FAIL - validator unavailable: {}".format(exc), file=sys.stderr)
        return 1
    result = validate_paths(
        [task_path, report_path],
        cross_check=True,
        target_dir=os.path.dirname(task_path),
    )
    if result.get("ok"):
        print("CHECK: PASS - report matches the task contract: {}".format(report_path))
        return 0
    print("CHECK: FAIL - report does not match the task contract:", file=sys.stderr)
    for line in format_validation_result(result):
        print("  " + str(line), file=sys.stderr)
    print(
        "  fix: regenerate with afc-report.py; do not hand-edit the report.",
        file=sys.stderr,
    )
    return 1


def main():
    parser = argparse.ArgumentParser(
        description="Write a compact report with validated enums and guardrails."
    )
    parser.add_argument("--task", required=True)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the existing report at the task's report_path and exit.",
    )
    parser.add_argument("--verdict", choices=sorted(VERDICTS))
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--evidence-ref", action="append", default=[])
    parser.add_argument(
        "--trust-level",
        choices=sorted(TRUST_LEVELS),
        default="referenced",
    )
    parser.add_argument(
        "--validation-tier",
        choices=sorted(VALIDATION_TIERS),
    )
    parser.add_argument(
        "--validation-result",
        choices=sorted(VALIDATION_RESULTS),
    )
    parser.add_argument("--summary")
    parser.add_argument("--remaining-risk", default="none")
    parser.add_argument("--reported-at", default=date.today().isoformat())
    parser.add_argument("--output")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.check:
        return check_report(os.path.abspath(args.task))

    missing = [
        name
        for name, value in (
            ("--verdict", args.verdict),
            ("--validation-result", args.validation_result),
            ("--summary", args.summary),
            ("--evidence-ref", args.evidence_ref),
        )
        if not value
    ]
    if missing:
        print(
            "error: write mode requires {}".format(", ".join(missing)),
            file=sys.stderr,
        )
        return 1

    placeholder_hits = [
        value
        for value in (list(args.evidence_ref) + [args.summary, args.remaining_risk])
        if value and TODO_RE.search(str(value))
    ]
    if placeholder_hits:
        print(
            "error: replace placeholder 'TODO' text with real values before "
            "reporting: {}".format("; ".join(placeholder_hits)),
            file=sys.stderr,
        )
        return 1

    if len(args.summary) > 600:
        print("error: --summary must be <= 600 characters", file=sys.stderr)
        return 1
    for label, values in (
        ("--changed-file", args.changed_file),
        ("--evidence-ref", args.evidence_ref),
    ):
        if any("\n" in value or "\r" in value for value in values):
            print(
                "error: {} values must be single-line".format(label),
                file=sys.stderr,
            )
            return 1
    task_path = os.path.abspath(args.task)
    task, error = parse_task(task_path)
    if error:
        print("error: {}".format(error), file=sys.stderr)
        return 1
    if task.get("schema") != "agent-file-coordination/task":
        print("error: --task is not an AFC task file", file=sys.stderr)
        return 1
    if not args.validation_tier:
        args.validation_tier = str(task.get("validation_tier") or "")
    declared_output = task.get("report_path")
    if not declared_output:
        print("error: no report output path was supplied", file=sys.stderr)
        return 1
    output = resolve_output_path(task_path, declared_output)
    task_inbox = os.path.dirname(task_path)
    if not path_is_within(output, task_inbox):
        print(
            "error: task report_path must stay inside the task inbox",
            file=sys.stderr,
        )
        return 1
    if args.output:
        requested_output = resolve_output_path(task_path, args.output)
        if os.path.normcase(requested_output) != os.path.normcase(output):
            print(
                "error: --output must match the task report_path",
                file=sys.stderr,
            )
            return 1

    content, errors = build_report(task, args)
    if errors:
        for reason in errors:
            print("error: {}".format(reason), file=sys.stderr)
        return 1
    size = len(content.encode("utf-8"))
    if size > REPORT_BUDGET_BYTES:
        print(
            "error: report is {} bytes; hard budget is {} bytes".format(
                size, REPORT_BUDGET_BYTES
            ),
            file=sys.stderr,
        )
        return 1
    if args.dry_run:
        print(content)
        return 0
    if os.path.exists(output) and not args.replace:
        print("error: report already exists: {}".format(output), file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(output), exist_ok=True)
    temp = None
    try:
        descriptor, temp = tempfile.mkstemp(
            prefix=os.path.basename(output) + ".",
            suffix=".tmp",
            dir=os.path.dirname(output),
            text=True,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.replace(temp, output)
        temp = None
    except OSError as exc:
        if temp:
            try:
                os.remove(temp)
            except OSError:
                pass
        print("error: failed to write report: {}".format(exc), file=sys.stderr)
        return 1
    print("Wrote {} ({} bytes)".format(output, size))
    marker = str(task.get("completion_marker") or "").strip()
    if marker:
        print(
            "Final chat line (paste verbatim as the last line of your reply): "
            "{}".format(marker)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
