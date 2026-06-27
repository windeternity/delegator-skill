#!/usr/bin/env python3
"""Close one task by moving its active task/report files into archive."""

import os
import sys
from datetime import date

from afc_event import add_event_context, append_event_once
from afc_frontmatter import parse_frontmatter_flat


CLOSED_STATUSES = {
    "CLOSED_GO",
    "CLOSED_PARTIAL",
    "CLOSED_RED",
    "CANCELLED",
    "SUPERSEDED",
}


def parse_frontmatter(filepath):
    return parse_frontmatter_flat(
        filepath, strict=False, include_content=True
    )


def write_status(filepath, content, status):
    lines = content.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip():
            start = i
            break
    if start is None:
        raise ValueError("empty file")
    end = None
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise ValueError("missing closing frontmatter")

    replaced = False
    for i in range(start + 1, end):
        raw = lines[i]
        if raw.strip().startswith("status:"):
            prefix = raw[:len(raw) - len(raw.lstrip())]
            lines[i] = "{}status: {}".format(prefix, status)
            replaced = True
            break
    if not replaced:
        raise ValueError("task file missing status")

    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")


def move_files_transactionally(destinations):
    moved = []
    try:
        for src, dest in destinations:
            os.rename(src, dest)
            moved.append((src, dest))
    except OSError as exc:
        rollback_errors = []
        for moved_src, moved_dest in reversed(moved):
            try:
                os.rename(moved_dest, moved_src)
            except OSError as rollback_exc:
                rollback_errors.append("{}: {}".format(moved_dest, rollback_exc))
        if rollback_errors:
            raise OSError(
                "{}; rollback also failed: {}".format(exc, "; ".join(rollback_errors))
            ) from exc
        raise


def scan_task_and_reports(inbox_dir, task_id):
    task = None
    reports = []
    for entry in sorted(os.listdir(inbox_dir)):
        path = os.path.join(inbox_dir, entry)
        if not os.path.isfile(path) or not entry.endswith(".md"):
            continue
        data, content, err = parse_frontmatter(path)
        if err or not data:
            continue
        schema = data.get("schema", "")
        if data.get("task_id", "").strip() != task_id:
            continue
        item = {"path": path, "filename": entry, "data": data, "content": content}
        if schema == "agent-file-coordination/task":
            if task is not None:
                raise ValueError("duplicate task_id '{}' in active inbox".format(task_id))
            task = item
        elif schema == "agent-file-coordination/report":
            reports.append(item)
    return task, reports


def usage():
    return (
        "usage: python -B scripts/afc-close.py --task-id TASK_ID "
        "--status CLOSED_GO|CLOSED_PARTIAL|CLOSED_RED|CANCELLED|SUPERSEDED "
        "[--dry-run] [INBOX_DIR]"
    )


def main():
    args = sys.argv[1:]
    dry_run = False
    task_id = None
    status = None
    positional = []

    i = 0
    while i < len(args):
        if args[i] == "--dry-run":
            dry_run = True
        elif args[i] == "--task-id":
            if i + 1 >= len(args):
                print("error: --task-id requires a value", file=sys.stderr)
                return 1
            task_id = args[i + 1].strip()
            i += 1
        elif args[i] == "--status":
            if i + 1 >= len(args):
                print("error: --status requires a value", file=sys.stderr)
                return 1
            status = args[i + 1].strip().upper()
            i += 1
        elif args[i] in ("--help", "-h"):
            print(usage())
            return 0
        elif args[i].startswith("--"):
            print("error: unknown flag {}".format(args[i]), file=sys.stderr)
            return 1
        else:
            positional.append(args[i])
        i += 1

    if not task_id:
        print("error: --task-id is required", file=sys.stderr)
        print(usage(), file=sys.stderr)
        return 1
    if status not in CLOSED_STATUSES:
        print("error: --status must be one of {}".format(", ".join(sorted(CLOSED_STATUSES))), file=sys.stderr)
        return 1
    if len(positional) > 1:
        print("error: expected at most one INBOX_DIR", file=sys.stderr)
        return 1

    inbox_dir = positional[0] if positional else ".agent-inbox"
    if not os.path.isdir(inbox_dir):
        print("error: directory not found: {}".format(inbox_dir), file=sys.stderr)
        return 1
    inbox_dir = os.path.abspath(inbox_dir)

    try:
        task, reports = scan_task_and_reports(inbox_dir, task_id)
    except ValueError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    if task is None:
        print("error: no active task found for task_id '{}'".format(task_id), file=sys.stderr)
        return 1

    archive_month = date.today().strftime("%Y-%m")
    archive_dir = os.path.join(inbox_dir, "archive", archive_month)
    files = [task] + reports
    destinations = [(item["path"], os.path.join(archive_dir, item["filename"])) for item in files]
    for _, dest in destinations:
        if os.path.exists(dest):
            print("error: archive target already exists: {}".format(dest), file=sys.stderr)
            return 1

    if dry_run:
        print("Would update task status to {} and move {} file(s) to {}".format(status, len(files), archive_dir))
        for src, dest in destinations:
            print("MOVE: {} -> {}".format(src, dest))
        print("Would append TASK_CLOSED event for {}".format(task_id))
        return 0

    os.makedirs(archive_dir, exist_ok=True)
    try:
        move_files_transactionally(destinations)
    except OSError as exc:
        print("error: failed to move files: {}".format(exc), file=sys.stderr)
        return 1

    archived_task_path = destinations[0][1]
    try:
        write_status(archived_task_path, task["content"], status)
    except (OSError, ValueError) as exc:
        try:
            move_files_transactionally([(dest, src) for src, dest in reversed(destinations)])
        except OSError as rollback_exc:
            print(
                "error: failed to update archived task status: {}; rollback failed: {}".format(
                    exc, rollback_exc
                ),
                file=sys.stderr,
            )
            return 1
        print("error: failed to update archived task status: {}; move rolled back".format(exc), file=sys.stderr)
        return 1

    closed_at = date.today().isoformat()
    event = {
        "schema": "agent-file-coordination/event",
        "schema_version": "0.1.0",
        "event_id": "evt-{}-closed-{}".format(task_id, closed_at),
        "event_type": "TASK_CLOSED",
        "task_id": task_id,
        "agent_name": task["data"].get("agent_name", ""),
        "status": status,
        "created_at": closed_at,
        "archive_path": archive_dir,
        "summary": "Closed task {} as {} and archived {} file(s).".format(
            task_id, status, len(files)
        ),
    }
    events_path = os.path.join(inbox_dir, "events.jsonl")
    try:
        append_event_once(events_path, add_event_context(event, task["data"], "closure"))
    except OSError as exc:
        print("error: failed to append TASK_CLOSED event: {}".format(exc), file=sys.stderr)
        return 1

    print("Closed {} as {}".format(task_id, status))
    print("Moved {} file(s) to {}".format(len(files), archive_dir))
    print("Appended TASK_CLOSED event to {}".format(events_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
