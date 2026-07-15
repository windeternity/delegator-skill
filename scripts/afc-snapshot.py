#!/usr/bin/env python3
"""Print a compact, read-only coordinator snapshot for an agent inbox."""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

from afc_frontmatter import parse_frontmatter_flat
from afc_roster import roster_status
from afc_constants import (
    CLOSED_STATUSES,
    REPORT_BUDGET_BYTES,
    REVIEW_REPORT_BUDGET_BYTES,
    TASK_BUDGET_BYTES,
)


def parse_session_preferences(roster_text):
    """Parse the SESSION PREFERENCES HTML comment block."""
    m = re.search(r"<!--\s*SESSION PREFERENCES\s*\n(.*?)-->", roster_text, re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    prefs = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("Change policy"):
            continue
        for label, key in [
            ("Default CAL", "default_cal"),
            ("Execution preference", "execution_preference"),
            ("Available resources", "available_resources"),
            ("Available now", "available_now"),
            ("Model preference order", "model_preference_order"),
            ("Avoid / unavailable", "avoid_unavailable"),
            ("Smoke tests", "smoke_tests"),
            ("Confirmed", "confirmed"),
        ]:
            if line.startswith(label + ":"):
                prefs[key] = line[len(label) + 1:].strip()
                break
    return prefs


def is_cal_configured(prefs):
    """Return True if SESSION PREFERENCES has a non-placeholder CAL default."""
    cal = prefs.get("default_cal", "")
    if not cal:
        return False
    if "CAL-1_OR_CAL-2_OR_CAL-3" in cal or "<" in cal:
        return False
    return cal in {"CAL-1", "CAL-2", "CAL-3"}


def cal_default_recorded(inbox_dir):
    """Check if CAL default is recorded in AGENT_ROSTER.md."""
    return roster_status(inbox_dir).get("cal_default_recorded") == "yes"




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


def recommend_next_action(data, inbox_dir):
    """Return a structured next-action summary."""
    roster = roster_status(inbox_dir)
    cal_recorded = roster.get("cal_default_recorded") == "yes"
    route_required = not data["active_tasks"] and not data["reports_waiting"]

    active_tasks = len(data["active_tasks"])
    new_reports = len(data["reports_waiting"])
    rejected_reports = "not_evaluated"
    stale_tasks = "not_evaluated"

    # Determine recommended action
    # Priority: active inbox work comes before CAL setup (read-only advisory only)
    if data["reports_waiting"]:
        recommended_action = "review_report"
    elif data["closed_unarchived"]:
        recommended_action = "close_task"
    elif data["active_tasks"]:
        recommended_action = "wait_for_reports"
    elif not cal_recorded:
        recommended_action = "ask_cal"
    elif roster.get("roster_status") != "usable":
        recommended_action = "ask_roster"
    elif route_required:
        recommended_action = "route_direct"
    else:
        recommended_action = "no_action"

    # Build read_next: up to 3 most important files
    read_next = []
    if data["reports_waiting"]:
        for report in data["reports_waiting"][:3]:
            read_next.append(report.get("path", ""))
    elif data["active_tasks"] and not data["reports_waiting"]:
        for task in data["active_tasks"][:3]:
            read_next.append(task.get("path", ""))

    # Build run_next: the single most useful command
    run_next = []
    if recommended_action == "review_report" and data["reports_waiting"]:
        run_next.append(f'python -B scripts/validate-agent-inbox.py "{inbox_dir}"')
    elif recommended_action == "ask_cal":
        run_next.append(f'python -B scripts/afc-first-run-config.py --inbox "{inbox_dir}" --print-questionnaire')
    elif recommended_action == "close_task" and data["closed_unarchived"]:
        task_id = data["closed_unarchived"][0].get("task_id", "")
        if task_id:
            run_next.append(f'python -B scripts/afc-close.py --dry-run --task-id "{task_id}" "{inbox_dir}"')

    return {
        "route_required": route_required,
        "cal_default_recorded": cal_recorded,
        "roster_status": roster.get("roster_status"),
        "external_worker_routes": roster.get("external_worker_routes"),
        "cal3_callable_routes": roster.get("cal3_callable_routes"),
        "roster_blocking_reason": roster.get("blocking_reason"),
        "active_tasks": active_tasks,
        "new_reports": new_reports,
        "rejected_reports": rejected_reports,
        "stale_tasks": stale_tasks,
        "recommended_next_action": recommended_action,
        "read_next": [p for p in read_next if p],
        "run_next": run_next,
    }


def main():
    args = sys.argv[1:]
    json_mode = False
    brief = False
    next_action_mode = False
    positional = []

    for arg in args:
        if arg == "--json":
            json_mode = True
        elif arg == "--brief":
            brief = True
        elif arg == "--next-action":
            next_action_mode = True
        elif arg in ("--help", "-h"):
            print("usage: python -B scripts/afc-snapshot.py [--brief] [--json] [--next-action] [INBOX_DIR]")
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

    # --next-action mode: compact, session-orientation summary
    if next_action_mode:
        na = recommend_next_action(inbox_data, inbox_dir)
        if json_mode:
            print(json.dumps(na, indent=2, ensure_ascii=False))
        else:
            print("route_required: {}".format(na["route_required"]))
            print("cal_default_recorded: {}".format(na["cal_default_recorded"]))
            print("roster_status: {}".format(na["roster_status"]))
            print("external_worker_routes: {}".format(na["external_worker_routes"]))
            print("cal3_callable_routes: {}".format(na["cal3_callable_routes"]))
            print("roster_blocking_reason: {}".format(na["roster_blocking_reason"]))
            print("active_tasks: {}".format(na["active_tasks"]))
            print("new_reports: {}".format(na["new_reports"]))
            print("rejected_reports: {}".format(na["rejected_reports"]))
            print("stale_tasks: {}".format(na["stale_tasks"]))
            print("recommended_next_action: {}".format(na["recommended_next_action"]))
            print("read_next:")
            for path in na["read_next"]:
                print("- {}".format(path))
            print("run_next:")
            for cmd in na["run_next"]:
                print("- {}".format(cmd))
        return 0

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
