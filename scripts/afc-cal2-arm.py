#!/usr/bin/env python3
"""Arm CAL-2 auto intake in one coordinator operation.

Records TASK_DISPATCHED for one or more existing tasks, then starts the
foreground afc-watch.py inbox consumer. This is intentionally thin: task
generation, worker reporting, and final intake remain separate commands.

Usage:
    python -B scripts/afc-cal2-arm.py --inbox <INBOX_DIR> --task-id <ID> [--task-id <ID> ...]

A parallel batch (more than one --task-id) waits once for all N reports by
default (one consolidated coordinator wake). Pass --incremental to re-arm per
worker, or --expected-reports N to wake on a smaller quorum.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date

try:
    from afc_event import add_event_context, append_event_once
    from afc_frontmatter import parse_frontmatter_flat
    from afc_roster import require_usable_roster, format_roster_block, maybe_warn_roster
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from afc_event import add_event_context, append_event_once
    from afc_frontmatter import parse_frontmatter_flat
    from afc_roster import require_usable_roster, format_roster_block, maybe_warn_roster


SKIP_DIRS = {"archive", "artifacts", "__pycache__"}


def parse_frontmatter(filepath):
    """Parse a small YAML-like frontmatter block into a flat dict."""
    return parse_frontmatter_flat(filepath, strict=False)


def iter_markdown_files(inbox_dir):
    """Yield Markdown files under the active inbox, excluding archive/artifacts."""
    for root, dirs, files in os.walk(inbox_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in sorted(files):
            if filename.endswith(".md"):
                yield os.path.join(root, filename)


def find_task(inbox_dir, task_id):
    """Return task metadata for task_id, or (None, error)."""
    matches = []
    for filepath in iter_markdown_files(inbox_dir):
        data, _ = parse_frontmatter(filepath)
        if not data:
            continue
        if data.get("schema") != "agent-file-coordination/task":
            continue
        if data.get("task_id", "").strip() == task_id:
            data["_filepath"] = filepath
            matches.append(data)

    if not matches:
        return None, "no task file found for task_id '{}'".format(task_id)
    if len(matches) > 1:
        return None, "duplicate task files found for task_id '{}'".format(task_id)
    return matches[0], None


def has_dispatched_event(events_path, task_id):
    """Return True if events.jsonl already contains TASK_DISPATCHED."""
    if not os.path.isfile(events_path):
        return False
    try:
        with open(events_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    event.get("event_type") == "TASK_DISPATCHED"
                    and event.get("task_id") == task_id
                ):
                    return True
    except OSError:
        return False
    return False


def dispatched_event(task_data, created_at):
    """Build a TASK_DISPATCHED event for a parsed task frontmatter dict."""
    task_id = task_data.get("task_id", "").strip()
    agent_name = task_data.get("agent_name", "").strip()
    event = {
        "schema": "agent-file-coordination/event",
        "schema_version": "0.1.0",
        "event_id": "evt-{}-dispatched".format(task_id),
        "event_type": "TASK_DISPATCHED",
        "task_id": task_id,
        "agent_name": agent_name,
        "created_at": created_at,
        "summary": "Handoff dispatched to {}.".format(agent_name),
    }
    marker = task_data.get("completion_marker", "").strip()
    if marker:
        event["completion_marker"] = marker
    return add_event_context(event, task_data, "dispatch")


def path_is_within(path, parent):
    try:
        return os.path.commonpath(
            [os.path.normcase(path), os.path.normcase(parent)]
        ) == os.path.normcase(parent)
    except ValueError:
        return False


def resolve_report_for_watcher(inbox_dir, task_data):
    """Return inbox-relative expected report path for a task, or (None, error)."""
    report_path = task_data.get("report_path", "").strip()
    task_id = task_data.get("task_id", "").strip()
    if not report_path:
        return None, "task '{}' is missing report_path".format(task_id)

    normalized = report_path.replace("\\", "/")
    if normalized.startswith(".agent-inbox/"):
        return normalized[len(".agent-inbox/"):], None
    if os.path.isabs(report_path):
        candidate = os.path.abspath(report_path)
    else:
        candidate = os.path.abspath(os.path.join(inbox_dir, report_path))

    inbox_abs = os.path.abspath(inbox_dir)
    if path_is_within(candidate, inbox_abs):
        rel = os.path.relpath(candidate, inbox_abs)
        return rel.replace("\\", "/"), None

    return None, "task '{}' report_path is outside inbox: {}".format(
        task_id, report_path
    )


def build_watcher_command(args, tasks):
    """Return the foreground watcher command for this CAL-2 arm."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cmd = [
        sys.executable,
        "-B",
        os.path.join(script_dir, "afc-watch.py"),
        "--json",
    ]
    if args.max_iterations is not None:
        cmd.extend(["--max-iterations", str(args.max_iterations)])
    if args.poll_interval is not None:
        cmd.extend(["--poll-interval", str(args.poll_interval)])
    if args.stale_threshold is not None:
        cmd.extend(["--stale-threshold", str(args.stale_threshold)])
    if args.auto_archive:
        cmd.append("--auto-archive")
    if len(tasks) == 1:
        expected_report, err = resolve_report_for_watcher(args.inbox, tasks[0])
        if err:
            raise ValueError(err)
        cmd.extend(["--expected-report", expected_report])
        cmd.extend(["--expected-task-id", tasks[0].get("task_id", "").strip()])
    else:
        for task_data in tasks:
            task_id = task_data.get("task_id", "").strip()
            if task_id:
                cmd.extend(["--expected-task-id", task_id])
        # Default a parallel batch to one consolidated wake after all N reports
        # arrive, instead of re-arming once per worker. --incremental opts back
        # into the per-report flow; --expected-reports sets a custom quorum.
        if not args.incremental:
            expected = (
                args.expected_reports
                if args.expected_reports is not None
                else len(tasks)
            )
            cmd.extend(["--expected-reports", str(expected)])
    cmd.append(args.inbox)
    return cmd


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Record CAL-2 dispatch events and arm afc-watch.py."
    )
    parser.add_argument("--inbox", required=True, help="agent-inbox directory")
    parser.add_argument(
        "--task-id",
        action="append",
        required=True,
        help="task_id to mark as dispatched; repeat for a batch",
    )
    parser.add_argument(
        "--created-at",
        default=date.today().isoformat(),
        help="YYYY-MM-DD event date (default: today)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-iterations", type=int)
    parser.add_argument("--poll-interval", type=int)
    parser.add_argument("--stale-threshold", type=int)
    parser.add_argument("--auto-archive", action="store_true")
    parser.add_argument(
        "--expected-reports",
        type=int,
        help="for a parallel batch, wake once after this many schema-valid "
             "reports arrive (default: the number of --task-id given). Ignored "
             "for a single task, which always uses scoped expected-report wait.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="process a batch one report per wake (re-arm per worker) instead "
             "of the default single consolidated wake.",
    )
    args = parser.parse_args(argv)

    args.inbox = os.path.abspath(args.inbox)
    if not os.path.isdir(args.inbox):
        print("error: inbox directory not found: {}".format(args.inbox), file=sys.stderr)
        return 1

    task_ids = []
    for task_id in args.task_id:
        task_id = task_id.strip()
        if task_id and task_id not in task_ids:
            task_ids.append(task_id)
    if not task_ids:
        print("error: at least one non-empty --task-id is required", file=sys.stderr)
        return 1
    if args.incremental and args.expected_reports is not None:
        print(
            "error: --incremental and --expected-reports are mutually exclusive",
            file=sys.stderr,
        )
        return 1
    if args.expected_reports is not None and not (1 <= args.expected_reports <= len(task_ids)):
        print(
            "error: --expected-reports must be between 1 and the number of "
            "--task-id given ({})".format(len(task_ids)),
            file=sys.stderr,
        )
        return 1
    if len(task_ids) == 1 and (args.incremental or args.expected_reports is not None):
        print(
            "note: --incremental/--expected-reports are ignored for a single "
            "task; using scoped expected-report wait.",
            file=sys.stderr,
        )
    if args.max_iterations is not None and args.max_iterations <= 1:
        print(
            "CAL2_PREFLIGHT_ONLY: --max-iterations <= 1 is not a real CAL-2 wait.",
            file=sys.stderr,
        )

    # --auto-archive only takes effect on the single/incremental watch loops;
    # the consolidated batch wait (_run_batch_wait) never calls
    # _check_auto_archive. For a multi-task arm with --auto-archive, fall back
    # to the per-report incremental flow so archiving still happens, rather than
    # silently dropping it and waiting for the whole batch.
    if args.auto_archive and len(task_ids) > 1 and not args.incremental:
        args.incremental = True
        dropped = (
            " (ignoring --expected-reports)"
            if args.expected_reports is not None
            else ""
        )
        args.expected_reports = None
        print(
            "note: --auto-archive forces the per-report (incremental) flow for "
            "a batch{}; the consolidated wake does not archive.".format(dropped),
            file=sys.stderr,
        )

    tasks = []
    for task_id in task_ids:
        task_data, err = find_task(args.inbox, task_id)
        if err:
            print("error: {}".format(err), file=sys.stderr)
            return 1
        tasks.append(task_data)

    # Per-task roster fail-closed gate (O3b): proving the roster has SOME usable
    # external route is not enough — EACH task's agent_name must be a usable
    # rostered route, since arm is a dispatch-producing entrypoint. Runs before
    # any TASK_DISPATCHED event or watcher side effect, and before the
    # --dry-run short-circuit. require_cal3=False is a safe backstop: a CAL-3
    # dispatch reaching this armer via run_watch() has already passed the
    # stricter require_cal3=True gate in afc-cal3-dispatch.py.
    for task_data in tasks:
        agent_name = task_data.get("agent_name", "").strip()
        if not agent_name:
            # A blank agent_name cannot be verified against the roster, and
            # roster_status() only applies its per-agent filter when agent_name
            # is truthy — so reject it explicitly rather than letting the gate
            # degrade to "any usable route".
            print(
                "ROSTER_BLOCKED: task '{}' has no agent_name; an external route "
                "cannot be verified".format(task_data.get("task_id", "")),
                file=sys.stderr,
            )
            return 1
        ok, status = require_usable_roster(
            args.inbox,
            agent_name=agent_name,
            require_cal3=False,
        )
        if not ok:
            print(format_roster_block(status), file=sys.stderr)
            return 1

    # The roster warning (e.g. legacy-fallback nudge) is roster-source level,
    # identical across tasks; emit once from the last task's status.
    maybe_warn_roster(status)

    events_path = os.path.join(args.inbox, "events.jsonl")
    for task_data in tasks:
        task_id = task_data.get("task_id", "").strip()
        if has_dispatched_event(events_path, task_id):
            print(
                "CAL-2 dispatch already recorded for task '{}'.".format(task_id),
                file=sys.stderr,
            )
            continue
        if args.dry_run:
            print(
                "Would append TASK_DISPATCHED for task '{}' to {}".format(
                    task_id, events_path
                )
            )
            continue
        event = dispatched_event(task_data, args.created_at)
        try:
            appended = append_event_once(events_path, event)
        except OSError as exc:
            print(
                "error: failed to append dispatch event: {}".format(exc),
                file=sys.stderr,
            )
            return 1
        status = "recorded" if appended else "already present"
        print(
            "CAL-2 dispatch {} for task '{}'.".format(status, task_id),
            file=sys.stderr,
        )

    try:
        watcher_cmd = build_watcher_command(args, tasks)
    except ValueError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    if args.dry_run:
        print("Would run: {}".format(subprocess.list2cmdline(watcher_cmd)))
        return 0

    return subprocess.call(watcher_cmd)


if __name__ == "__main__":
    sys.exit(main())
