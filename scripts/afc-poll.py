#!/usr/bin/env python3
"""Poll an agent-inbox directory for newly-arrived report files.

Runs afc-status.py once to refresh STATUS.md, then scans for Markdown files
whose frontmatter contains ``schema: agent-file-coordination/report`` and
compares their mtimes against a persisted state file to detect new or updated
reports. Prints a coordinator-oriented next_action list.

Reports are detected by frontmatter schema, NOT by filename prefix. Any
``.md`` file in the inbox with ``schema: agent-file-coordination/report`` in
its YAML frontmatter is treated as a report, regardless of its filename.

Python stdlib only. Python 3.8+ compatible. Windows + POSIX safe.

Usage:
    python -B scripts/afc-poll.py [--state-file PATH] [--json] [--dry-run] <INBOX_DIR>

Exit codes:
    0   success (with or without new reports)
    1   INBOX_DIR missing, afc-status.py failure, or corrupt state file
"""

import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone

from afc_event import (
    add_event_context,
    append_event_once,
    report_event_id,
)
from afc_frontmatter import parse_frontmatter_flat
from afc_fsutil import atomic_write
from afc_constants import (
    CLOSED_STATUSES,
    REPORT_BUDGET_BYTES,
    REVIEW_REPORT_BUDGET_BYTES,
    TASK_BUDGET_BYTES,
)

# I3 hygiene hint constants
ACTIVE_INBOX_HINT_LIMIT_BYTES = 100 * 1024

# Stale undispatched hint threshold (days)
STALE_UNDISPATCHED_DAYS = 1


def _find_afc_status():
    """Locate afc-status.py relative to this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "afc-status.py")
    if os.path.isfile(path):
        return path
    return None


def _load_state(state_path):
    """Load the poll state JSON file.

    Returns dict {filename: mtime_iso_string} or empty dict if file
    does not exist. Raises ValueError on corrupt file.
    """
    if not os.path.isfile(state_path):
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"corrupt state file {state_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"state file is not a JSON object: {state_path}")
    return data


def _save_state(state_path, state):
    """Persist the poll state dict as JSON via afc_fsutil.atomic_write."""
    encoded = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    if not atomic_write(state_path, encoded):
        raise OSError("failed to write state file: {}".format(state_path))


def _mtime_iso(filepath):
    """Return file mtime as ISO 8601 string (UTC)."""
    mtime = os.path.getmtime(filepath)
    dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_frontmatter(filepath):
    return parse_frontmatter_flat(filepath, strict=False)


def _scan_reports(inbox_dir):
    """Return dict {filename: filepath} for files with report schema frontmatter.

    Detects reports by ``schema: agent-file-coordination/report`` in YAML
    frontmatter, NOT by filename prefix. Any ``.md`` file in the inbox with
    the report schema is treated as a report regardless of its name.
    """
    reports = {}
    try:
        entries = os.listdir(inbox_dir)
    except OSError as exc:
        raise OSError(f"cannot list {inbox_dir}: {exc}") from exc
    for entry in sorted(entries):
        if not entry.endswith(".md"):
            continue
        filepath = os.path.join(inbox_dir, entry)
        if not os.path.isfile(filepath):
            continue
        data, _ = _parse_frontmatter(filepath)
        if data and data.get("schema") == "agent-file-coordination/report":
            reports[entry] = filepath
    return reports


def _find_task_metadata(inbox_dir, task_id):
    """Return frontmatter for the task matching task_id, or an empty dict."""
    try:
        entries = os.listdir(inbox_dir)
    except OSError:
        return {}
    for entry in sorted(entries):
        if not entry.endswith(".md"):
            continue
        filepath = os.path.join(inbox_dir, entry)
        data, _ = _parse_frontmatter(filepath)
        if (data and
                data.get("schema") == "agent-file-coordination/task" and
                data.get("task_id", "").strip() == task_id):
            return data
    return {}


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
    report_items = reports.values() if hasattr(reports, "values") else reports
    for report in report_items:
        filepath = report.get("filepath")
        if filepath and filepath not in seen_paths:
            seen_paths.add(filepath)
            try:
                total_bytes += os.path.getsize(filepath)
            except OSError:
                pass
    return total_bytes


def _compute_hints(inbox_dir):
    """Compute deterministic advisory HINT: lines for active-inbox hygiene drift.

    Returns list of hint strings (single-line, deterministic, advisory).
    Scripts must never act on hints.
    """
    hints = []

    # Scan all .md files for task schema to detect closed states
    closed_count = 0
    tasks = {}
    reports = []
    try:
        entries = os.listdir(inbox_dir)
    except OSError:
        return hints

    for entry in sorted(entries):
        filepath = os.path.join(inbox_dir, entry)
        if not os.path.isfile(filepath):
            continue

        if not entry.endswith(".md"):
            continue
        data, _ = _parse_frontmatter(filepath)
        if not data:
            continue
        if data.get("schema") == "agent-file-coordination/task":
            status = data.get("status", "").strip().upper()
            task_id = data.get("task_id", "").strip()
            created_at = data.get("created_at", "").strip()
            if status in CLOSED_STATUSES:
                closed_count += 1
            if task_id:
                tasks[task_id] = {
                    "status": status,
                    "created_at": created_at,
                    "role": data.get("role", "").strip(),
                    "filepath": filepath,
                }
        elif data.get("schema") == "agent-file-coordination/report":
            reports.append({
                "task_id": data.get("task_id", "").strip(),
                "filepath": filepath,
            })

    total_bytes = _active_inbox_size_bytes(tasks, reports)

    # Hint 1: closed/cancelled/superseded task files still in active inbox
    if closed_count > 0:
        hints.append(
            f"HINT: {closed_count} closed task/report files in active inbox"
            f" — archive to .agent-inbox/archive/<YYYY-MM>/"
        )

    # Hint 2: active inbox size over threshold
    if total_bytes > ACTIVE_INBOX_HINT_LIMIT_BYTES:
        hints.append(
            f"HINT: active inbox is {total_bytes // 1024} KB"
            f" — archive or summarize before the next coordinator turn"
        )

    # Hint 3: task/report size budget warnings (advisory only)
    oversized_tasks = []
    for task_id, task_info in tasks.items():
        try:
            size = os.path.getsize(task_info["filepath"])
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
    for report in reports:
        task = tasks.get(report["task_id"], {})
        budget = REVIEW_REPORT_BUDGET_BYTES if task.get("role") == "reviewer" else REPORT_BUDGET_BYTES
        try:
            size = os.path.getsize(report["filepath"])
        except OSError:
            continue
        if size > budget:
            oversized_reports.append(report["task_id"] or report["filepath"])
    if oversized_reports:
        hints.append(
            f"WARN: {len(oversized_reports)} report file(s) exceed report budget"
            f" — summarize evidence and reference artifacts/<task-id>/ paths"
        )

    # Hint 4: stale undispatched ASSIGNED tasks
    dispatched = _load_dispatched_tasks(inbox_dir)
    current_date = date.today()
    stale_undispatched = []
    for task_id, task_info in tasks.items():
        if task_info["status"] != "ASSIGNED":
            continue
        if task_id in dispatched:
            continue
        created_at = task_info.get("created_at", "")
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
    args = sys.argv[1:]
    state_file = None
    json_mode = False
    dry_run = False
    positional = []

    i = 0
    while i < len(args):
        if args[i] == "--state-file":
            if i + 1 >= len(args):
                print("error: --state-file requires a PATH", file=sys.stderr)
                return 1
            state_file = args[i + 1]
            i += 1
        elif args[i] == "--json":
            json_mode = True
        elif args[i] == "--dry-run":
            dry_run = True
        elif args[i] == "--help" or args[i] == "-h":
            print(
                "afc-poll.py - poll an agent-inbox for newly-arrived report files.\n"
                "\n"
                "Runs afc-status.py once, then scans for .md files with\n"
                "schema: agent-file-coordination/report in their frontmatter\n"
                "and compares their mtimes against a persisted state file to\n"
                "detect new or updated reports. Reports are detected by\n"
                "frontmatter schema, not by filename prefix.\n"
                "\n"
                "Usage:\n"
                "    python -B scripts/afc-poll.py [--state-file PATH] [--json] [--dry-run] <INBOX_DIR>"
            )
            return 0
        elif args[i].startswith("--"):
            print(f"error: unknown flag {args[i]}", file=sys.stderr)
            return 1
        else:
            positional.append(args[i])
        i += 1

    if len(positional) != 1:
        print(
            "usage: python -B scripts/afc-poll.py [--state-file PATH] [--json] [--dry-run] <INBOX_DIR>",
            file=sys.stderr,
        )
        return 1

    inbox_dir = positional[0]

    if not os.path.isdir(inbox_dir):
        print(f"error: directory not found: {inbox_dir}", file=sys.stderr)
        return 1

    # Default state file location
    if state_file is None:
        state_file = os.path.join(inbox_dir, ".afc-poll-state.json")

    # Step 1: Run afc-status.py once
    afc_status = _find_afc_status()
    if afc_status is None:
        print("error: afc-status.py not found alongside this script", file=sys.stderr)
        return 1

    cmd = [sys.executable, "-B", afc_status]
    if dry_run:
        cmd.append("--no-write")
    cmd.append(inbox_dir)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        print(f"error: afc-status.py failed (exit {result.returncode}): {stderr}", file=sys.stderr)
        return 1

    # Step 2: Scan for report files
    try:
        reports = _scan_reports(inbox_dir)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Step 3: Load previous state
    try:
        prev_state = _load_state(state_file)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    # Step 4: Detect new or updated reports
    new_reports = []
    current_state = {}

    for filename in sorted(reports.keys()):
        filepath = reports[filename]
        mtime = _mtime_iso(filepath)
        current_state[filename] = mtime

        prev_mtime = prev_state.get(filename)
        if prev_mtime is None or mtime > prev_mtime:
            report_data, _ = _parse_frontmatter(filepath)
            new_reports.append({
                "filename": filename,
                "path": filepath,
                "mtime": mtime,
                "data": report_data or {},
            })

    # Step 5: Build output
    polled_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Persist report intake before advancing poll state. The event ID is stable
    # across poll and watch, so running both does not duplicate the event.
    if not dry_run:
        events_path = os.path.join(inbox_dir, "events.jsonl")
        for report in new_reports:
            task_id = report["data"].get("task_id", "").strip()
            if not task_id:
                continue
            task_data = _find_task_metadata(inbox_dir, task_id)
            event = {
                "schema": "agent-file-coordination/event",
                "schema_version": "0.1.0",
                "event_id": report_event_id(task_id, report["mtime"]),
                "event_type": "REPORT_RECEIVED",
                "task_id": task_id,
                "agent_name": report["data"].get("agent_name", ""),
                "created_at": polled_at[:10],
                "report_path": report["path"],
                "summary": "Detected schema-valid report {}.".format(
                    report["filename"]
                ),
            }
            add_event_context(event, task_data, "report_intake", polled_at)
            try:
                append_event_once(events_path, event)
            except OSError as exc:
                print(f"error: failed to append report event: {exc}", file=sys.stderr)
                return 1

    # I3: compute hygiene hints
    hints = _compute_hints(inbox_dir)

    if json_mode:
        output = {
            "polled_at": polled_at,
            "new_reports": [r["filename"] for r in new_reports],
            "next_actions": [
                f"coordinator should review {r['path']}" for r in new_reports
            ],
            "hints": hints,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        if new_reports:
            for r in new_reports:
                print(f"next_action: coordinator should review {r['path']}")
        else:
            print("no new reports")
        # I3: emit hints on text output
        for hint in hints:
            print(hint)

    # Step 6: Update state (skip in dry-run)
    if not dry_run:
        try:
            _save_state(state_file, current_state)
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
