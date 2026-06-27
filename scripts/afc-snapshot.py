#!/usr/bin/env python3
"""Print a compact, read-only coordinator snapshot for an agent inbox."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from afc_frontmatter import parse_frontmatter_flat


CLOSED_STATUSES = {
    "CLOSED_GO",
    "CLOSED_PARTIAL",
    "CLOSED_RED",
    "CANCELLED",
    "SUPERSEDED",
}
TASK_BUDGET_BYTES = 4 * 1024
REPORT_BUDGET_BYTES = 3 * 1024
REVIEW_REPORT_BUDGET_BYTES = 5 * 1024


def parse_frontmatter(filepath):
    return parse_frontmatter_flat(filepath, strict=False)


def git_summary(project_root):
    def run_git(args):
        result = subprocess.run(
            ["git"] + args,
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    branch = run_git(["branch", "--show-current"]) or "unknown"
    status = run_git(["status", "--short"])
    if status is None:
        return {"branch": branch, "dirty": "unknown", "dirty_files": 0}
    dirty_lines = [line for line in status.splitlines() if line.strip()]
    return {
        "branch": branch,
        "dirty": "dirty" if dirty_lines else "clean",
        "dirty_files": len(dirty_lines),
    }


def active_inbox_size(inbox_data):
    total = 0
    seen_paths = set()
    for task in inbox_data["tasks"].values():
        path = task.get("path")
        if path and path not in seen_paths:
            seen_paths.add(path)
            total += os.path.getsize(path)
    for report in inbox_data["reports"]:
        path = report.get("path")
        if path and path not in seen_paths:
            seen_paths.add(path)
            total += os.path.getsize(path)
    return total


def scan_inbox(inbox_dir):
    tasks = {}
    reports = []
    budget_warnings = []

    for entry in sorted(os.listdir(inbox_dir)):
        path = os.path.join(inbox_dir, entry)
        if not os.path.isfile(path) or not entry.endswith(".md"):
            continue
        data, err = parse_frontmatter(path)
        if err or not data:
            continue
        schema = data.get("schema", "")
        size = os.path.getsize(path)
        if schema == "agent-file-coordination/task":
            task_id = data.get("task_id", "").strip()
            if not task_id:
                continue
            tasks[task_id] = {
                "task_id": task_id,
                "agent_name": data.get("agent_name", ""),
                "role": data.get("role", ""),
                "status": data.get("status", "").strip().upper(),
                "path": path,
                "filename": entry,
                "size": size,
            }
            if size > TASK_BUDGET_BYTES:
                budget_warnings.append(
                    "task {} is {} B; suggested <= {} B".format(
                        task_id, size, TASK_BUDGET_BYTES
                    )
                )
        elif schema == "agent-file-coordination/report":
            task_id = data.get("task_id", "").strip()
            reports.append({
                "task_id": task_id,
                "agent_name": data.get("agent_name", ""),
                "path": path,
                "filename": entry,
                "size": size,
            })

    for report in reports:
        task = tasks.get(report["task_id"], {})
        budget = REVIEW_REPORT_BUDGET_BYTES if task.get("role") == "reviewer" else REPORT_BUDGET_BYTES
        if report["size"] > budget:
            budget_warnings.append(
                "report {} is {} B; suggested <= {} B".format(
                    report["filename"], report["size"], budget
                )
            )

    active_tasks = [
        task for task in tasks.values()
        if task["status"] not in CLOSED_STATUSES
    ]
    closed_unarchived = [
        task for task in tasks.values()
        if task["status"] in CLOSED_STATUSES
    ]
    report_task_ids = {report["task_id"] for report in reports}
    reports_waiting = [
        report for report in reports
        if tasks.get(report["task_id"], {}).get("status") not in CLOSED_STATUSES
    ]

    return {
        "tasks": tasks,
        "reports": reports,
        "active_tasks": active_tasks,
        "closed_unarchived": closed_unarchived,
        "reports_waiting": reports_waiting,
        "report_task_ids": report_task_ids,
        "budget_warnings": budget_warnings,
    }


def latest_events(inbox_dir, limit=5):
    path = os.path.join(inbox_dir, "events.jsonl")
    if not os.path.isfile(path):
        return []
    events = []
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append({
                "event_type": event.get("event_type", ""),
                "task_id": event.get("task_id", ""),
                "created_at": event.get("created_at", ""),
                "occurred_at": event.get("occurred_at", ""),
                "summary": event.get("summary", ""),
            })
    return events[-limit:]


def recommend(data):
    if data["reports_waiting"]:
        return "review_reports"
    if data["closed_unarchived"]:
        return "archive_closed_tasks"
    if data["active_tasks"]:
        return "wait_for_reports_or_run_next_worker"
    return "no_coordinator_action"


def main():
    args = sys.argv[1:]
    json_mode = False
    brief = False
    positional = []

    for arg in args:
        if arg == "--json":
            json_mode = True
        elif arg == "--brief":
            brief = True
        elif arg in ("--help", "-h"):
            print("usage: python -B scripts/afc-snapshot.py [--brief] [--json] [INBOX_DIR]")
            return 0
        elif arg.startswith("--"):
            print("error: unknown flag {}".format(arg), file=sys.stderr)
            return 1
        else:
            positional.append(arg)

    inbox_dir = positional[0] if positional else ".agent-inbox"
    if len(positional) > 1:
        print("error: expected at most one INBOX_DIR", file=sys.stderr)
        return 1
    if not os.path.isdir(inbox_dir):
        print("error: directory not found: {}".format(inbox_dir), file=sys.stderr)
        return 1

    inbox_dir = os.path.abspath(inbox_dir)
    project_root = os.path.dirname(inbox_dir) if os.path.basename(inbox_dir) == ".agent-inbox" else os.getcwd()
    inbox_data = scan_inbox(inbox_dir)
    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "inbox": inbox_dir,
        "git": git_summary(project_root),
        "active_inbox_size_bytes": active_inbox_size(inbox_data),
        "active_tasks": [
            {
                "task_id": task["task_id"],
                "agent_name": task["agent_name"],
                "role": task["role"],
                "status": task["status"],
                "filename": task["filename"],
            }
            for task in inbox_data["active_tasks"]
        ],
        "reports_waiting_for_review": [
            {
                "task_id": report["task_id"],
                "agent_name": report["agent_name"],
                "filename": report["filename"],
            }
            for report in inbox_data["reports_waiting"]
        ],
        "closed_but_unarchived_tasks": [
            {
                "task_id": task["task_id"],
                "agent_name": task["agent_name"],
                "status": task["status"],
                "filename": task["filename"],
            }
            for task in inbox_data["closed_unarchived"]
        ],
        "latest_events": latest_events(inbox_dir),
        "budget_warnings": inbox_data["budget_warnings"],
        "recommended_next_action": recommend(inbox_data),
    }

    if json_mode:
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0

    git = output["git"]
    if brief:
        print(
            "branch={} dirty={} active_tasks={} reports_waiting={} closed_unarchived={} next={}".format(
                git["branch"],
                git["dirty_files"],
                len(output["active_tasks"]),
                len(output["reports_waiting_for_review"]),
                len(output["closed_but_unarchived_tasks"]),
                output["recommended_next_action"],
            )
        )
        return 0

    print("# AFC Snapshot")
    print("git: {} ({}, {} dirty file(s))".format(git["branch"], git["dirty"], git["dirty_files"]))
    print("active_inbox_size: {} B".format(output["active_inbox_size_bytes"]))
    print("active_tasks: {}".format(len(output["active_tasks"])))
    for task in output["active_tasks"]:
        print("- {} [{}] {}".format(task["task_id"], task["status"], task["agent_name"]))
    print("reports_waiting_for_review: {}".format(len(output["reports_waiting_for_review"])))
    for report in output["reports_waiting_for_review"]:
        print("- {} -> {}".format(report["task_id"], report["filename"]))
    print("closed_but_unarchived_tasks: {}".format(len(output["closed_but_unarchived_tasks"])))
    for task in output["closed_but_unarchived_tasks"]:
        print("- {} [{}] {}".format(task["task_id"], task["status"], task["filename"]))
    if output["latest_events"]:
        print("latest_events:")
        for event in output["latest_events"]:
            when = event["occurred_at"] or event["created_at"]
            print("- {} {} {}".format(when, event["event_type"], event["task_id"]))
    for warning in output["budget_warnings"]:
        print("WARN: {}".format(warning))
    print("recommended_next_action: {}".format(output["recommended_next_action"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
