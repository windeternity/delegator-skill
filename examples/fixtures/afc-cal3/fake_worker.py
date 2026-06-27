#!/usr/bin/env python3
"""Small fake CAL-3 worker used by fixture tests."""

import argparse
import os
import subprocess
import sys
import time


def parse_frontmatter(path):
    data = {}
    with open(path, "r", encoding="utf-8-sig") as handle:
        lines = handle.read().splitlines()
    if not lines or lines[0].strip() != "---":
        return data
    current = None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if not line.strip() or line.strip().startswith("- "):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        indent = len(line) - len(line.lstrip())
        if indent > 0 and current:
            data[current + "." + key] = value
        else:
            data[key] = value
            current = key if value == "" else None
    return data


def resolve_report_path(task, task_path):
    report_path = task.get("report_path", "")
    if os.path.isabs(report_path):
        return report_path
    workspace = task.get("workspace.path", os.path.dirname(task_path))
    if report_path.replace("\\", "/").startswith(".agent-inbox/"):
        return os.path.abspath(os.path.join(workspace, report_path))
    return os.path.abspath(os.path.join(os.path.dirname(task_path), report_path))


def write_report(task, report_path):
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    content = """---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: {task_id}
agent_name: {agent_name}
verdict: GO
changed_files:
  - none
evidence_refs:
  - fake-worker
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
reported_at: 2026-06-19
---
# Fake Worker Report
""".format(
        task_id=task.get("task_id", ""),
        agent_name=task.get("agent_name", ""),
    )
    with open(report_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def write_invalid_report(task, report_path):
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    content = """---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: {task_id}
agent_name: {agent_name}
status: completed
changed_files:
  - none
---

Invalid report fixture.
""".format(
        task_id=task.get("task_id", ""),
        agent_name=task.get("agent_name", ""),
    )
    with open(report_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def write_guardrail_yes_report(task, report_path):
    write_report(task, report_path)
    with open(report_path, "r", encoding="utf-8") as handle:
        content = handle.read()
    content = content.replace(
        "  permission_scope_expanded: no",
        "  permission_scope_expanded: yes",
    )
    with open(report_path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def write_stray_source(task, task_path):
    workspace = task.get("workspace.path", os.path.dirname(task_path))
    with open(os.path.join(workspace, "STRAY.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# stray source change\n")


def edit_readme(task, task_path):
    workspace = task.get("workspace.path", os.path.dirname(task_path))
    with open(os.path.join(workspace, "README.md"), "a", encoding="utf-8", newline="\n") as handle:
        handle.write("worker edit\n")


def commit_source(task, task_path):
    workspace = task.get("workspace.path", os.path.dirname(task_path))
    path = os.path.join(workspace, "COMMIT_VIOLATION.md")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("# unauthorized commit\n")
    subprocess.run(["git", "-C", workspace, "add", "COMMIT_VIOLATION.md"], check=True)
    subprocess.run(
        ["git", "-C", workspace, "commit", "-m", "test: unauthorized worker commit"],
        check=True,
        capture_output=True,
        text=True,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument(
        "--mode",
        choices=[
            "success",
            "delayed-success",
            "no-report",
            "approval",
            "fail",
            "sleep",
            "stdin-approval",
            "invalid-report",
            "guardrail-yes",
            "stray-source",
            "stray-source-fail",
            "edit-readme",
            "commit-source",
        ],
        default="success",
    )
    parser.add_argument("--sleep", type=float, default=0.1)
    args = parser.parse_args(argv)

    task = parse_frontmatter(args.task)
    report_path = resolve_report_path(task, args.task)

    if args.mode == "sleep":
        time.sleep(args.sleep)
        return 0
    if args.mode == "stdin-approval":
        char = sys.stdin.read(1)
        if char == "":
            print("APPROVAL REQUIRED: stdin closed in headless mode")
            return 7
        time.sleep(args.sleep)
        return 0
    if args.mode == "delayed-success":
        time.sleep(args.sleep)
        write_report(task, report_path)
        print("fake worker wrote report after delay")
        return 0
    if args.mode == "approval":
        print("APPROVAL REQUIRED: permission prompt blocked automation")
        print("task path: .agent-inbox/task-mimo-readonly.md")
        print("token=secret-value " + "s" + "k-" + "abcdefghijklmnopqrstuvwxyz")
        return 7
    if args.mode == "fail":
        print("worker failed")
        return 2
    if args.mode == "no-report":
        print("done but intentionally no report")
        return 0
    if args.mode == "invalid-report":
        write_invalid_report(task, report_path)
        print("fake worker wrote invalid report")
        return 0
    if args.mode == "guardrail-yes":
        write_guardrail_yes_report(task, report_path)
        print("fake worker wrote guardrail yes report")
        return 0
    if args.mode == "stray-source":
        write_stray_source(task, args.task)
        write_report(task, report_path)
        print("fake worker wrote stray source and report")
        return 0
    if args.mode == "stray-source-fail":
        write_stray_source(task, args.task)
        print("fake worker wrote stray source then failed")
        return 2
    if args.mode == "edit-readme":
        edit_readme(task, args.task)
        write_report(task, report_path)
        print("fake worker edited README and wrote report")
        return 0
    if args.mode == "commit-source":
        commit_source(task, args.task)
        write_report(task, report_path)
        print("fake worker committed source and wrote report")
        return 0

    write_report(task, report_path)
    print("fake worker wrote report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
