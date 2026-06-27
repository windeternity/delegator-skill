#!/usr/bin/env python3
"""Generate STATUS.md from task and report files in an agent-inbox directory.

Python stdlib only. Scans Markdown files in <INBOX_DIR>, identifies task and
report files by frontmatter schema, matches reports to tasks by task_id, and
generates a schema-valid STATUS.md with the canonical nine columns sorted by
task_id.

Usage:
    python -B scripts/afc-status.py [--dry-run] [--no-write] [--summary-only] [--updated-at YYYY-MM-DD] <INBOX_DIR>

Exit codes:
    0   STATUS.md generated (or printed in dry-run mode)
    1   validation failure (missing directory, no tasks, malformed frontmatter,
        duplicate task IDs, duplicate reports, orphan reports)
"""

import json
import os
import sys
from datetime import date, timedelta

from afc_event import add_event_context, append_event_once
from afc_frontmatter import parse_frontmatter_flat as parse_frontmatter
from afc_fsutil import atomic_write

# I3 hygiene hint constants
ACTIVE_INBOX_HINT_LIMIT_BYTES = 100 * 1024
TASK_BUDGET_BYTES = 4 * 1024
REPORT_BUDGET_BYTES = 3 * 1024
REVIEW_REPORT_BUDGET_BYTES = 5 * 1024
CLOSED_GO = "CLOSED_GO"
CLOSED_PARTIAL = "CLOSED_PARTIAL"
CLOSED_RED = "CLOSED_RED"
CANCELLED = "CANCELLED"
SUPERSEDED = "SUPERSEDED"
CLOSED_STATUSES = (CLOSED_GO, CLOSED_PARTIAL, CLOSED_RED, CANCELLED, SUPERSEDED)

# Stale undispatched hint threshold (days)
STALE_UNDISPATCHED_DAYS = 1


def next_action_for(task_status, has_report):
    """Determine next_action from task status and report presence."""
    if has_report:
        return "coordinator_review"
    s = task_status.upper()
    if s == "DRAFT":
        return "assign_worker"
    if s in ("ASSIGNED", "RUNNING"):
        return "wait_for_report"
    if s in ("REPORTED", "REVIEWING"):
        return "coordinator_review"
    if s == "NEEDS_FIX":
        return "needs_fix_task"
    if s == "BLOCKED":
        return "blocked"
    # CLOSED_GO, CLOSED_PARTIAL, CLOSED_RED, CANCELLED, SUPERSEDED
    return "close_task"


def escape_cell(text):
    """Escape pipe characters and line breaks for Markdown table cells."""
    return str(text).replace("|", "\\|").replace("\n", " ")


def _load_dispatched_tasks(inbox_dir):
    """Load set of task_ids that have TASK_DISPATCHED events in events.jsonl.

    Returns set of task_id strings.
    """
    dispatched = set()
    events_path = os.path.join(inbox_dir, "events.jsonl")
    if not os.path.isfile(events_path):
        return dispatched
    try:
        with open(events_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                    if evt.get("event_type") == "TASK_DISPATCHED":
                        task_id = evt.get("task_id", "").strip()
                        if task_id:
                            dispatched.add(task_id)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return dispatched


def _active_inbox_size_bytes(tasks, reports):
    """Return bytes for top-level task/report files in the active working set."""
    total_bytes = 0
    seen_paths = set()
    for task in tasks.values():
        filepath = task.get("filepath")
        if filepath and filepath not in seen_paths:
            seen_paths.add(filepath)
            try:
                total_bytes += os.path.getsize(filepath)
            except OSError:
                pass
    for report in reports.values():
        filepath = report.get("filepath")
        if filepath and filepath not in seen_paths:
            seen_paths.add(filepath)
            try:
                total_bytes += os.path.getsize(filepath)
            except OSError:
                pass
    return total_bytes


def _compute_hints(inbox_dir, tasks, reports=None, updated_at=None):
    """Compute deterministic advisory HINT: lines for active-inbox hygiene drift.

    Returns list of hint strings (single-line, deterministic, advisory).
    Scripts must never act on hints.
    """
    hints = []

    # Hint 1: closed/cancelled/superseded task files still in active inbox
    closed_count = 0
    for task_id, task in tasks.items():
        if task["status"].upper() in CLOSED_STATUSES:
            closed_count += 1
    if closed_count > 0:
        hints.append(
            f"HINT: {closed_count} closed task/report files in active inbox"
            f" — archive to .agent-inbox/archive/<YYYY-MM>/"
        )

    # Hint 2: active inbox size over threshold
    total_bytes = _active_inbox_size_bytes(tasks, reports)
    if total_bytes > ACTIVE_INBOX_HINT_LIMIT_BYTES:
        hints.append(
            f"HINT: active inbox is {total_bytes // 1024} KB"
            f" — archive or summarize before the next coordinator turn"
        )

    # Hint 3: task/report size budget warnings (advisory only)
    oversized_tasks = []
    for task_id, task in tasks.items():
        try:
            size = os.path.getsize(task["filepath"])
        except OSError:
            continue
        if size > TASK_BUDGET_BYTES:
            oversized_tasks.append(task_id)
    if oversized_tasks:
        hints.append(
            f"WARN: {len(oversized_tasks)} task file(s) exceed {TASK_BUDGET_BYTES} B budget"
            f" — keep task briefs compact and move logs to artifacts/<task-id>/"
        )

    oversized_reports = []
    if reports:
        for task_id, report in reports.items():
            try:
                size = os.path.getsize(report["filepath"])
            except OSError:
                continue
            task = tasks.get(task_id, {})
            budget = REVIEW_REPORT_BUDGET_BYTES if task.get("role") == "reviewer" else REPORT_BUDGET_BYTES
            if size > budget:
                oversized_reports.append(task_id)
    if oversized_reports:
        hints.append(
            f"WARN: {len(oversized_reports)} report file(s) exceed report budget"
            f" — summarize evidence and reference artifacts/<task-id>/ paths"
        )

    # Hint 4: stale undispatched ASSIGNED tasks
    if updated_at is None:
        updated_at = date.today().isoformat()
    try:
        current_date = date.fromisoformat(updated_at)
    except (ValueError, TypeError):
        current_date = date.today()

    dispatched = _load_dispatched_tasks(inbox_dir)
    stale_undispatched = []
    for task_id, task in tasks.items():
        if task["status"].upper() != "ASSIGNED":
            continue
        if task_id in dispatched:
            continue
        # Check age from created_at
        created_at = task.get("created_at", "")
        if created_at:
            try:
                created_date = date.fromisoformat(created_at)
                age_days = (current_date - created_date).days
                if age_days >= STALE_UNDISPATCHED_DAYS:
                    stale_undispatched.append(task_id)
            except (ValueError, TypeError):
                pass

    if stale_undispatched:
        hints.append(
            f"HINT: {len(stale_undispatched)} ASSIGNED task(s) without dispatch confirmation"
            f" — verify handoff was delivered"
        )

    return hints


def main():
    # Parse arguments
    args = sys.argv[1:]
    dry_run = False
    no_write = False
    summary_only = False
    updated_at = None

    positional = []
    i = 0
    while i < len(args):
        if args[i] == "--dry-run":
            dry_run = True
        elif args[i] == "--no-write":
            no_write = True
        elif args[i] == "--summary-only":
            summary_only = True
            no_write = True
        elif args[i] == "--updated-at":
            if i + 1 >= len(args):
                print("error: --updated-at requires a YYYY-MM-DD value", file=sys.stderr)
                return 1
            updated_at = args[i + 1]
            i += 1
        elif args[i].startswith("--"):
            print(f"error: unknown flag {args[i]}", file=sys.stderr)
            return 1
        else:
            positional.append(args[i])
        i += 1

    if len(positional) != 1:
        print("usage: python -B scripts/afc-status.py [--dry-run] [--no-write] [--summary-only] [--updated-at YYYY-MM-DD] <INBOX_DIR>", file=sys.stderr)
        return 1

    inbox_dir = positional[0]

    if not os.path.isdir(inbox_dir):
        print(f"error: directory not found: {inbox_dir}", file=sys.stderr)
        return 1

    if updated_at is None:
        from datetime import date
        updated_at = date.today().isoformat()

    # Scan for task and report files
    tasks = {}      # task_id -> {task_id, agent_name, role, protocol_mode, status, workspace_path, report_path, filepath}
    reports = {}    # task_id -> {task_id, filepath}

    try:
        entries = os.listdir(inbox_dir)
    except OSError as exc:
        print(f"error: cannot list {inbox_dir}: {exc}", file=sys.stderr)
        return 1

    for entry in sorted(entries):
        if not entry.endswith(".md"):
            continue
        filepath = os.path.join(inbox_dir, entry)
        data, err = parse_frontmatter(filepath)
        if err:
            print(f"error: {err}", file=sys.stderr)
            return 1

        schema = data.get("schema", "")

        if schema == "agent-file-coordination/task":
            task_id = data.get("task_id", "").strip()
            if not task_id:
                print(f"error: task file missing task_id: {filepath}", file=sys.stderr)
                return 1
            if task_id in tasks:
                print(f"error: duplicate task_id '{task_id}' in {tasks[task_id]['filepath']} and {filepath}", file=sys.stderr)
                return 1

            # Validate required fields (B3 brief: task_id, agent_name, role,
            # protocol_mode, status, workspace.path, report_path)
            for field in ("task_id", "agent_name", "role", "protocol_mode", "status", "report_path"):
                if not data.get(field):
                    print(f"error: task {task_id} missing required field '{field}'", file=sys.stderr)
                    return 1

            workspace_path = data.get("workspace.path", "")
            if not workspace_path:
                print(f"error: task {task_id} missing required field 'workspace.path'", file=sys.stderr)
                return 1
            report_path = data.get("report_path", "")

            tasks[task_id] = {
                "task_id": task_id,
                "agent_name": data.get("agent_name", ""),
                "role": data.get("role", ""),
                "protocol_mode": data.get("protocol_mode", ""),
                "status": data.get("status", ""),
                "created_at": data.get("created_at", ""),
                "workspace_path": workspace_path,
                "report_path": report_path,
                "filepath": filepath,
            }

        elif schema == "agent-file-coordination/report":
            task_id = data.get("task_id", "").strip()
            if not task_id:
                print(f"error: report file missing task_id: {filepath}", file=sys.stderr)
                return 1
            if task_id in reports:
                print(f"error: duplicate report for task_id '{task_id}': {reports[task_id]['filepath']} and {filepath}", file=sys.stderr)
                return 1
            reports[task_id] = {"task_id": task_id, "filepath": filepath}

    if not tasks:
        # Produce a valid zero-row STATUS.md when no active tasks exist
        # (long-lived inbox with only archived content is valid state)
        pass

    # Check for orphan reports
    for task_id, info in reports.items():
        if task_id not in tasks:
            print(f"error: orphan report for unknown task_id '{task_id}': {info['filepath']}", file=sys.stderr)
            return 1

    # Load dispatch confirmation from events.jsonl
    dispatched = _load_dispatched_tasks(inbox_dir)

    # Compute status rows
    rows = []
    for task_id in sorted(tasks.keys()):
        task = tasks[task_id]
        has_report = task_id in reports
        effective_status = "REPORTED" if has_report else task["status"]
        na = next_action_for(effective_status, has_report)
        dispatched_status = "yes" if task_id in dispatched else "no"

        rows.append({
            "task_id": task_id,
            "assigned_agent": task["agent_name"],
            "role": task["role"],
            "protocol_mode": task["protocol_mode"],
            "status": effective_status,
            "dispatched": dispatched_status,
            "workspace": task["workspace_path"],
            "report_path": task["report_path"],
            "next_action": na,
        })

    # Build output
    out_lines = []
    out_lines.append("---")
    out_lines.append("schema: agent-file-coordination/status-board")
    out_lines.append(f"schema_version: 0.1.0")
    out_lines.append(f"updated_at: {updated_at}")
    out_lines.append("---")
    out_lines.append("")
    out_lines.append("# Status Board")
    out_lines.append("")
    out_lines.append("| task_id | assigned_agent | role | protocol_mode | status | dispatched | workspace | report_path | next_action |")
    out_lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in rows:
        cells = [
            escape_cell(row["task_id"]),
            escape_cell(row["assigned_agent"]),
            escape_cell(row["role"]),
            escape_cell(row["protocol_mode"]),
            escape_cell(row["status"]),
            escape_cell(row["dispatched"]),
            escape_cell(row["workspace"]),
            escape_cell(row["report_path"]),
            escape_cell(row["next_action"]),
        ]
        out_lines.append("| " + " | ".join(cells) + " |")
    out_lines.append("")
    output = "\n".join(out_lines)

    if dry_run or no_write:
        hints = _compute_hints(inbox_dir, tasks, reports, updated_at)
        if summary_only:
            active_count = sum(
                1 for task in tasks.values()
                if task["status"].upper() not in CLOSED_STATUSES
            )
            print(f"active_tasks: {active_count}")
            print(f"reports: {len(reports)}")
            print(f"closed_but_unarchived: {sum(1 for task in tasks.values() if task['status'].upper() in CLOSED_STATUSES)}")
        else:
            print(output)
        for hint in hints:
            print(hint)
        return 0

    # Write mode: atomic replace of STATUS.md + append to events.jsonl
    status_path = os.path.join(inbox_dir, "STATUS.md")
    events_path = os.path.join(inbox_dir, "events.jsonl")

    if not atomic_write(status_path, output):
        print(
            "error: failed to write STATUS.md (atomic write failed after retries)",
            file=sys.stderr,
        )
        return 1

    # Append STATUS_UPDATED event
    event = add_event_context({
        "schema": "agent-file-coordination/event",
        "schema_version": "0.1.0",
        "event_id": f"evt-status-{updated_at}",
        "event_type": "STATUS_UPDATED",
        "created_at": updated_at,
        "summary": f"Auto-generated STATUS.md with {len(rows)} task(s).",
    }, {}, "status")
    try:
        append_event_once(events_path, event)
    except OSError as exc:
        print(f"error: failed to append to events.jsonl: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {status_path}")
    print(f"Appended event to {events_path}")

    # I3: emit hygiene hints on stdout
    hints = _compute_hints(inbox_dir, tasks, reports, updated_at)
    for hint in hints:
        print(hint)

    return 0


if __name__ == "__main__":
    sys.exit(main())
