#!/usr/bin/env python3
"""Event-gated watcher for agent-inbox report arrivals.

Polls an agent-inbox directory for new schema-valid report files using
afc-poll.py's detection logic, validates report frontmatter before waking,
and fires a one-shot staleness alarm when an ASSIGNED task has no report
after a threshold.

The watcher exits on one of these wake events:
  report_ready    — a new schema-valid report was detected and validated
  report_rejected — a new report was detected but failed validation (exit 3)
  task_archived   — one coordinator-closed task was archived (--auto-archive)
  archive_blocked — automatic archive preflight failed (exit 1)
  stale_alarm     — a staleness threshold was exceeded (one-shot)
  error           — a fail-closed error occurred

The coordinator arms this script as the foreground inbox consumer. When it exits,
the coordinator reads the exit code and stdout to determine the wake event,
then acts (review report, investigate stale task, or handle error) and
re-arms the watcher.

Python stdlib only. Python 3.8+ compatible. Windows + POSIX safe.

Usage:
    python -B scripts/afc-watch.py [OPTIONS] <INBOX_DIR>

Options:
    --stale-threshold SECS   Staleness alarm threshold in seconds (default: 3600)
    --poll-interval SECS     Seconds between poll checks (default: 5)
    --max-iterations N       Maximum poll iterations before forced exit (default: 720)
    --expected-report PATH   Only wake for this report file (inbox-relative)
    --expected-task-id ID    Cross-check or filter task_id; repeat for a batch
    --auto-archive           Archive one validated terminal task, then exit
    --json                   Output wake event as JSON
    --help, -h               Show this help

Exit codes:
    0   report_ready, task_archived, or no_wake — read stdout to distinguish
    1   error or archive_blocked — fail-closed
    2   stale_alarm — staleness threshold exceeded (one-shot)
    3   report_rejected — a report failed validation (one-shot per rejection)
"""

import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from types import SimpleNamespace

try:
    from afc_event import (
        add_event_context,
        append_event_once,
        report_event_id,
    )
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from afc_event import (
        add_event_context,
        append_event_once,
        report_event_id,
    )

try:
    from afc_validation import validate_report_schema
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from afc_validation import validate_report_schema
try:
    from afc_fsutil import atomic_write, sweep_stale_tmp
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from afc_fsutil import atomic_write, sweep_stale_tmp
try:
    from afc_frontmatter import parse_frontmatter_nested, extract_structured_frontmatter
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from afc_frontmatter import parse_frontmatter_nested, extract_structured_frontmatter


# ---------------------------------------------------------------------------
# Frontmatter parsing (reused from afc-poll.py / afc-next.py pattern)
# ---------------------------------------------------------------------------

def _parse_frontmatter(filepath):
    return parse_frontmatter_nested(filepath, strict=False)


# ---------------------------------------------------------------------------
# Report detection (mirrors afc-poll.py scan logic)
# ---------------------------------------------------------------------------

def _scan_report_files(inbox_dir):
    """Return dict {filename: filepath} for files with report schema frontmatter."""
    reports = {}
    try:
        entries = os.listdir(inbox_dir)
    except OSError:
        return reports
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


def _load_state(state_path):
    """Load poll state JSON file. Returns dict or empty dict.

    Backward-compatible: old format {filename: mtime_string} is migrated
    to new format {filename: {mtime: str, status: "seen"}} on load.
    """
    if not os.path.isfile(state_path):
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        # Fail loud: a corrupt state file must not be silently reset to {},
        # which would re-flag every report still in the inbox as new and
        # cause duplicate intake. main() already handles this ValueError.
        raise ValueError(
            "corrupt state file {}: {}".format(state_path, exc)
        ) from exc

    # Migrate old flat format: {filename: mtime_string}
    migrated = {}
    for key, value in raw.items():
        if isinstance(value, str):
            migrated[key] = {"mtime": value, "status": "seen"}
        elif isinstance(value, dict):
            migrated[key] = value
        else:
            # Unknown format; treat as seen
            migrated[key] = {"mtime": str(value), "status": "seen"}
    return migrated


def _save_state(state_path, state, retries=5, delay=0.1):
    """Persist poll state dict as JSON atomically.

    Delegates to afc_fsutil.atomic_write (Windows-safe retry + direct-write
    fallback + guaranteed .tmp cleanup). Returns True on success, False on
    failure; never corrupts the prior state file.
    """
    encoded = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
    return atomic_write(state_path, encoded, retries=retries, delay=delay)


def _mtime_iso(filepath):
    """Return file mtime as ISO 8601 string (UTC)."""
    mtime = os.path.getmtime(filepath)
    dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Task scanning (for staleness detection)
# ---------------------------------------------------------------------------

def _scan_tasks(inbox_dir):
    """Return dict {task_id: task_info} for task files."""
    tasks = {}
    try:
        entries = os.listdir(inbox_dir)
    except OSError:
        return tasks
    for entry in sorted(entries):
        if not entry.endswith(".md"):
            continue
        filepath = os.path.join(inbox_dir, entry)
        if not os.path.isfile(filepath):
            continue
        data, _ = _parse_frontmatter(filepath)
        if not data or data.get("schema") != "agent-file-coordination/task":
            continue
        task_id = data.get("task_id", "").strip()
        if not task_id:
            continue
        tasks[task_id] = {
            "task_id": task_id,
            "status": data.get("status", "").strip().upper(),
            "agent_name": data.get("agent_name", "").strip(),
            "created_at": data.get("created_at", "").strip(),
            "trace_id": data.get("trace_id", "").strip(),
            "coordinator_thread_id": data.get(
                "coordinator_thread_id", ""
            ).strip(),
            "coordinator_root_thread_id": data.get(
                "coordinator_root_thread_id", ""
            ).strip(),
            "filepath": filepath,
        }
    return tasks


def _scan_report_task_ids(inbox_dir):
    """Return set of task_ids that have report files."""
    report_task_ids = set()
    try:
        entries = os.listdir(inbox_dir)
    except OSError:
        return report_task_ids
    for entry in sorted(entries):
        if not entry.endswith(".md"):
            continue
        filepath = os.path.join(inbox_dir, entry)
        if not os.path.isfile(filepath):
            continue
        data, _ = _parse_frontmatter(filepath)
        if data and data.get("schema") == "agent-file-coordination/report":
            tid = data.get("task_id", "").strip()
            if tid:
                report_task_ids.add(tid)
    return report_task_ids


def _scan_valid_reports(inbox_dir, task_index=None):
    """Return (valid_task_ids, rejected_task_ids) for report files in the inbox.

    A report counts as valid only if it passes the same schema validation the
    single-report watcher path uses, so a batch wait never resolves on a
    malformed or over-budget report.

    When ``task_index`` is supplied (from _load_task_index), it is reused for
    every report's task cross-check so the scan stays O(reports + tasks).
    """
    valid = set()
    rejected = set()
    try:
        entries = os.listdir(inbox_dir)
    except OSError:
        return valid, rejected
    # Build the task index once for the whole scan so validating N reports
    # stays O(N + tasks) instead of O(N * tasks) frontmatter parses.
    if task_index is None:
        task_index = _load_task_index(inbox_dir)
    for entry in sorted(entries):
        if not entry.endswith(".md"):
            continue
        filepath = os.path.join(inbox_dir, entry)
        if not os.path.isfile(filepath):
            continue
        data, _ = _parse_frontmatter(filepath)
        if not data or data.get("schema") != "agent-file-coordination/report":
            continue
        tid = data.get("task_id", "").strip()
        if not tid:
            continue
        ok, _reasons = _validate_report(filepath, task_index=task_index)
        if ok:
            valid.add(tid)
        else:
            rejected.add(tid)
    return valid, rejected


# ---------------------------------------------------------------------------
# Report validation (uses shared afc_validation module)
# ---------------------------------------------------------------------------

def _load_task_data_for_report(inbox_dir, report_data):
    """Return the full task frontmatter dict matching a report's task_id.

    Used to feed validate_report_schema's optional task cross-checks so the
    watcher rejects the same agent_name/coordination_mode/comparison_group
    mismatches that afc-intake.py does. Returns None when no matching task
    file is present (non-fatal: cross-checks simply do not run in that case).

    This is the single-report path: it scans the inbox once for one lookup,
    which is O(tasks). Batch/poll loops that validate many reports per pass
    should build a task index once via _load_task_index and pass it as
    ``task_index`` to _validate_report instead, to stay linear.
    """
    task_id = str(report_data.get("task_id") or "").strip()
    if not task_id:
        return None
    return _load_task_index(inbox_dir).get(task_id)


def _load_task_index(inbox_dir):
    """Return {task_id: full task frontmatter dict} for task files in the inbox.

    Build once per scan/pass and pass to _validate_report as ``task_index`` so
    validating N reports stays O(N + tasks) instead of O(N * tasks).
    """
    index = {}
    try:
        entries = os.listdir(inbox_dir)
    except OSError:
        return index
    for entry in sorted(entries):
        if not entry.endswith(".md"):
            continue
        filepath = os.path.join(inbox_dir, entry)
        if not os.path.isfile(filepath):
            continue
        data, _ = _parse_frontmatter(filepath)
        if not data or data.get("schema") != "agent-file-coordination/task":
            continue
        task_id = str(data.get("task_id") or "").strip()
        if task_id:
            index[task_id] = data
    return index


def _validate_report(filepath, inbox_dir=None, task_index=None):
    """Validate a report file using the shared validation helper.

    Returns (is_valid, reasons_list). Fail-closed: any parsing error or
    missing required field returns (False, [reasons]).

    Task cross-checks (agent_name / coordination_mode / comparison_group /
    modify_source) run when a matching task is available, so the watcher
    rejects the same mismatches afc-intake.py does. Supply the task either as
    a pre-built ``task_index`` (preferred in batch/poll loops — build it once
    with _load_task_index) or via ``inbox_dir`` (single-report path, which
    scans the inbox once for the lookup). Without either, a report could pass
    the watcher but be rejected at intake.
    """
    # Structured parse preserves list-block fields (evidence_refs etc.) as
    # real lists; the flat/nested parser collapses them to "", which would
    # bypass validate_report_schema's non-empty-list check. Matches the
    # canonical validator (afc_inbox_validation) contract.
    data, body, errs = extract_structured_frontmatter(filepath)
    if errs:
        return False, ["parse error: {}".format("; ".join(errs))]
    if not data:
        return False, ["no frontmatter" if data is None else "empty frontmatter"]
    if data.get("schema") != "agent-file-coordination/report":
        return False, ["wrong schema: {}".format(data.get("schema"))]

    task = None
    if task_index is not None:
        tid = str(data.get("task_id") or "").strip()
        task = task_index.get(tid) if tid else None
    elif inbox_dir is not None:
        task = _load_task_data_for_report(inbox_dir, data)
    is_valid, reasons = validate_report_schema(data, body=body, task=task)
    return is_valid, reasons


# ---------------------------------------------------------------------------
# Staleness detection
# ---------------------------------------------------------------------------

CLOSED_STATUSES = {
    "CLOSED_GO",
    "CLOSED_PARTIAL",
    "CLOSED_RED",
    "CANCELLED",
    "SUPERSEDED",
}


def _script_path(filename):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def _compact_process_error(result):
    text = (result.stderr or result.stdout or "").strip()
    if not text:
        return "exit {}".format(result.returncode)
    return " ".join(text.split())[:500]


def _attempt_auto_archive(inbox_dir):
    """Archive at most one validated terminal task."""
    tasks = _scan_tasks(inbox_dir)
    terminal_ids = sorted(
        task_id
        for task_id, info in tasks.items()
        if info.get("status") in CLOSED_STATUSES
    )
    if not terminal_ids:
        return None

    status_preflight = subprocess.run(
        [
            sys.executable,
            "-B",
            _script_path("afc-status.py"),
            "--no-write",
            inbox_dir,
        ],
        capture_output=True,
        text=True,
    )
    if status_preflight.returncode != 0:
        return {
            "state": "blocked",
            "task_id": terminal_ids[0],
            "message": "status preflight failed: {}".format(
                _compact_process_error(status_preflight)
            ),
        }

    validator = subprocess.run(
        [
            sys.executable,
            "-B",
            _script_path("validate-agent-inbox.py"),
            "--active-only",
            inbox_dir,
        ],
        capture_output=True,
        text=True,
    )
    if validator.returncode != 0:
        return {
            "state": "blocked",
            "task_id": terminal_ids[0],
            "message": "active inbox validation failed: {}".format(
                _compact_process_error(validator)
            ),
        }

    task_id = terminal_ids[0]
    task = tasks[task_id]
    matching_reports = []
    for filename, filepath in _scan_report_files(inbox_dir).items():
        report_data, _ = _parse_frontmatter(filepath)
        if report_data and report_data.get("task_id", "").strip() == task_id:
            matching_reports.append(filename)

    if len(matching_reports) != 1:
        return {
            "state": "blocked",
            "task_id": task_id,
            "message": (
                "terminal task requires exactly one validated report; found {}"
            ).format(len(matching_reports)),
        }

    close_result = subprocess.run(
        [
            sys.executable,
            "-B",
            _script_path("afc-close.py"),
            "--task-id",
            task_id,
            "--status",
            task["status"],
            inbox_dir,
        ],
        capture_output=True,
        text=True,
    )
    if close_result.returncode != 0:
        return {
            "state": "blocked",
            "task_id": task_id,
            "message": "archive helper failed: {}".format(
                _compact_process_error(close_result)
            ),
        }

    status_result = subprocess.run(
        [
            sys.executable,
            "-B",
            _script_path("afc-status.py"),
            inbox_dir,
        ],
        capture_output=True,
        text=True,
    )
    if status_result.returncode != 0:
        return {
            "state": "error",
            "task_id": task_id,
            "message": "task archived but STATUS.md refresh failed: {}".format(
                _compact_process_error(status_result)
            ),
        }

    post_validate = subprocess.run(
        [
            sys.executable,
            "-B",
            _script_path("validate-agent-inbox.py"),
            "--active-only",
            inbox_dir,
        ],
        capture_output=True,
        text=True,
    )
    if post_validate.returncode != 0:
        return {
            "state": "error",
            "task_id": task_id,
            "message": "task archived but post-validation failed: {}".format(
                _compact_process_error(post_validate)
            ),
        }

    archive_dir = os.path.join(
        os.path.abspath(inbox_dir), "archive", date.today().strftime("%Y-%m")
    )
    return {
        "state": "archived",
        "task_id": task_id,
        "archive_path": archive_dir,
        "message": "archived terminal task {} as {}".format(
            task_id, task["status"]
        ),
    }


def _report_brief(report):
    """Return bounded report metadata for JSON wake summaries."""
    item = {
        "filename": report.get("filename", ""),
        "task_id": report.get("task_id", ""),
    }
    if report.get("path"):
        item["report_path"] = report["path"]
    reasons = report.get("reasons")
    if reasons:
        item["rejection_reasons"] = reasons[:5]
    return item


def _wake_extra(ready_reports, rejected_reports, next_action_hint):
    """Build optional JSON-only wake fields."""
    extra = {}
    if ready_reports:
        extra["ready_reports"] = [
            _report_brief(report) for report in ready_reports[:10]
        ]
    if rejected_reports:
        extra["rejected_reports"] = [
            _report_brief(report) for report in rejected_reports[:10]
        ]
    if next_action_hint:
        extra["next_action_hint"] = next_action_hint
    return extra


def _find_oldest_stale_task(inbox_dir, stale_threshold_secs,
                            expected_task_ids=None):
    """Find the oldest ASSIGNED task without a report that exceeds threshold.

    Returns (task_id, age_seconds) or (None, 0) if no stale task found.

    Age source semantics:
    - If created_at contains a time component (ISO 8601 datetime), use
      the parsed datetime directly (preserves exact datetime contract).
    - If created_at is date-only (YYYY-MM-DD with no 'T'), use the
      task file's mtime as a precise sub-day age source.  Date-only
      created_at would otherwise be interpreted as 00:00 UTC, causing
      fresh tasks to appear hundreds of minutes old immediately.
    """
    now = datetime.now(timezone.utc)
    expected_task_ids = set(expected_task_ids or [])
    tasks = _scan_tasks(inbox_dir)
    report_task_ids = _scan_report_task_ids(inbox_dir)

    oldest = None
    oldest_age = 0

    for task_id, info in tasks.items():
        if expected_task_ids and task_id not in expected_task_ids:
            continue
        if info["status"] != "ASSIGNED":
            continue
        if task_id in report_task_ids:
            continue
        created_at = info.get("created_at", "")
        if not created_at:
            continue

        # Determine age source: file mtime for date-only, parsed
        # datetime for full ISO 8601 datetimes.
        is_date_only = "T" not in created_at
        if is_date_only:
            try:
                task_mtime = os.path.getmtime(info["filepath"])
                age = now.timestamp() - task_mtime
            except OSError:
                continue
        else:
            try:
                created = datetime.fromisoformat(created_at)
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age = (now - created).total_seconds()
            except (ValueError, TypeError):
                continue

        if age >= stale_threshold_secs:
            if oldest is None or age > oldest_age:
                oldest = task_id
                oldest_age = age

    return oldest, oldest_age


# ---------------------------------------------------------------------------
# Expected-report rejection helper
# ---------------------------------------------------------------------------

def _reject_expected(json_mode, filepath, filename, mtime, reasons,
                     prev_state, state_file, inbox_dir):
    """Handle rejection of an expected report: save state, emit event, log."""
    reasons_text = "; ".join(reasons)

    # Log to stderr
    print(
        "watch: rejected expected report {}: {}".format(filename, reasons_text),
        file=sys.stderr,
    )

    # Save state (only this one file)
    next_state = dict(prev_state)
    next_state[filename] = {
        "mtime": mtime,
        "status": "rejected",
        "rejection_reasons": reasons,
    }
    _save_state(state_file, next_state)

    # Emit REPORT_REJECTED event
    occurred_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report_data, _ = _parse_frontmatter(filepath)
    task_id = ""
    agent_name = ""
    if report_data:
        task_id = report_data.get("task_id", "").strip()
        agent_name = report_data.get("agent_name", "").strip()

    event = {
        "schema": "agent-file-coordination/event",
        "schema_version": "0.1.0",
        "event_id": "REPORT_REJECTED-{}-{}".format(
            task_id or "unknown", mtime),
        "event_type": "REPORT_REJECTED",
        "task_id": task_id,
        "agent_name": agent_name,
        "created_at": occurred_at[:10],
        "report_path": filepath,
        "summary": "Report rejected during watcher intake: {}".format(
            reasons_text),
    }
    if task_id:
        task_data = _scan_tasks(inbox_dir).get(task_id, {})
        add_event_context(event, task_data, "report_intake", occurred_at)
    else:
        event["occurred_at"] = occurred_at
        event["phase"] = "report_intake"

    events_path = os.path.join(inbox_dir, "events.jsonl")
    if os.path.isfile(events_path):
        try:
            append_event_once(events_path, event)
        except OSError:
            pass  # non-fatal

    _emit(json_mode, "report_rejected", task_id,
          "{} rejected: {}".format(filename, reasons_text),
          filepath, reasons)


# ---------------------------------------------------------------------------
# Main watcher loop
# ---------------------------------------------------------------------------

def parse_args(argv):
    """Parse and validate CLI arguments.

    Returns (options, exit_code): on success (SimpleNamespace, None); on
    --help (None, 0); on any usage error (None, 1) after printing to stderr.
    """
    args = list(argv)
    stale_threshold = 3600
    poll_interval = 5
    max_iterations = 720
    json_mode = False
    expected_report = None
    expected_task_ids = []
    expected_reports = None
    auto_archive = False
    positional = []

    i = 0
    while i < len(args):
        if args[i] == "--stale-threshold":
            if i + 1 >= len(args):
                print("error: --stale-threshold requires SECS", file=sys.stderr)
                return None, 1
            try:
                stale_threshold = int(args[i + 1])
            except ValueError:
                print("error: --stale-threshold must be an integer", file=sys.stderr)
                return None, 1
            i += 1
        elif args[i] == "--poll-interval":
            if i + 1 >= len(args):
                print("error: --poll-interval requires SECS", file=sys.stderr)
                return None, 1
            try:
                poll_interval = int(args[i + 1])
            except ValueError:
                print("error: --poll-interval must be an integer", file=sys.stderr)
                return None, 1
            i += 1
        elif args[i] == "--max-iterations":
            if i + 1 >= len(args):
                print("error: --max-iterations requires N", file=sys.stderr)
                return None, 1
            try:
                max_iterations = int(args[i + 1])
            except ValueError:
                print("error: --max-iterations must be an integer", file=sys.stderr)
                return None, 1
            i += 1
        elif args[i] == "--expected-report":
            if i + 1 >= len(args):
                print("error: --expected-report requires REPORT_PATH", file=sys.stderr)
                return None, 1
            expected_report = args[i + 1].strip()
            i += 1
        elif args[i] == "--expected-task-id":
            if i + 1 >= len(args):
                print("error: --expected-task-id requires TASK_ID", file=sys.stderr)
                return None, 1
            expected_task_id = args[i + 1].strip()
            if expected_task_id and expected_task_id not in expected_task_ids:
                expected_task_ids.append(expected_task_id)
            i += 1
        elif args[i] == "--expected-reports":
            if i + 1 >= len(args):
                print("error: --expected-reports requires N", file=sys.stderr)
                return None, 1
            try:
                expected_reports = int(args[i + 1])
            except ValueError:
                print("error: --expected-reports must be an integer", file=sys.stderr)
                return None, 1
            if expected_reports < 1:
                print("error: --expected-reports must be >= 1", file=sys.stderr)
                return None, 1
            i += 1
        elif args[i] == "--auto-archive":
            auto_archive = True
        elif args[i] == "--target":
            # Deprecated: use --expected-report instead
            print("error: --target is deprecated; use --expected-report <FILENAME>", file=sys.stderr)
            return None, 1
        elif args[i] == "--json":
            json_mode = True
        elif args[i] == "--help" or args[i] == "-h":
            print(
                "afc-watch.py - event-gated watcher for agent-inbox report arrivals.\n"
                "\n"
                "Polls an agent-inbox for new schema-valid reports and exits\n"
                "on: report_ready/task_archived (exit 0),\n"
                "    archive_blocked/error (exit 1), stale_alarm (exit 2),\n"
                "    or report_rejected (exit 3).\n"
                "\n"
                "Usage:\n"
                "    python -B scripts/afc-watch.py [OPTIONS] <INBOX_DIR>\n"
                "\n"
                "Options:\n"
                "    --stale-threshold SECS     Staleness alarm threshold (default: 3600)\n"
                "    --poll-interval SECS       Seconds between polls (default: 5)\n"
                "    --max-iterations N         Max poll iterations (default: 720)\n"
                "    --expected-report PATH     Only wake for this report file (inbox-relative)\n"
                "    --expected-task-id TASK_ID Cross-check or filter task_id; repeat for a batch\n"
                "    --expected-reports N       Block until N schema-valid reports arrive, then\n"
                "                               return once (batch parallel dispatch). A hung\n"
                "                               worker past --stale-threshold wakes early.\n"
                "    --auto-archive             Archive one validated terminal task, then exit\n"
                "    --json                     Output wake event as JSON\n"
            )
            return None, 0
        elif args[i].startswith("--"):
            print("error: unknown flag {}".format(args[i]), file=sys.stderr)
            return None, 1
        else:
            positional.append(args[i])
        i += 1

    if len(positional) != 1:
        print(
            "usage: python -B scripts/afc-watch.py [OPTIONS] <INBOX_DIR>",
            file=sys.stderr,
        )
        return None, 1

    inbox_dir = positional[0]

    # Validate inbox exists
    if not os.path.isdir(inbox_dir):
        print("error: directory not found: {}".format(inbox_dir), file=sys.stderr)
        return None, 1

    # Validate stale threshold
    if stale_threshold < 1:
        print("error: --stale-threshold must be >= 1", file=sys.stderr)
        return None, 1

    # Validate and resolve --expected-report
    expected_report_path = None
    expected_report_filename = None
    if expected_report is not None:
        if len(expected_task_ids) > 1:
            print(
                "error: --expected-report accepts at most one --expected-task-id",
                file=sys.stderr,
            )
            return None, 1
        # Reject traversal attempts
        if ".." in expected_report.replace("\\", "/").split("/"):
            print("error: --expected-report must not contain path traversal", file=sys.stderr)
            return None, 1
        # Resolve: accept bare filename or inbox-relative path
        candidate = os.path.join(inbox_dir, expected_report)
        candidate = os.path.normpath(candidate)
        inbox_norm = os.path.normpath(inbox_dir)
        if not candidate.startswith(inbox_norm + os.sep) and candidate != inbox_norm:
            print("error: --expected-report must be inside the inbox directory", file=sys.stderr)
            return None, 1
        if not candidate.endswith(".md"):
            print("error: --expected-report must be a .md file", file=sys.stderr)
            return None, 1
        expected_report_path = candidate
        expected_report_filename = os.path.basename(candidate)

    opts = SimpleNamespace(
        stale_threshold=stale_threshold,
        poll_interval=poll_interval,
        max_iterations=max_iterations,
        json_mode=json_mode,
        expected_task_ids=expected_task_ids,
        expected_reports=expected_reports,
        auto_archive=auto_archive,
        inbox_dir=inbox_dir,
        expected_report_path=expected_report_path,
        expected_report_filename=expected_report_filename,
    )
    return opts, None


def _check_auto_archive(inbox_dir, json_mode):
    """Try to archive one terminal task.

    Returns an exit code if the archive resolved this iteration (the caller
    should return it), or None to continue polling.
    """
    archive_result = _attempt_auto_archive(inbox_dir)
    if archive_result is None:
        return None
    if archive_result["state"] == "archived":
        _emit(
            json_mode,
            "task_archived",
            archive_result["task_id"],
            archive_result["message"],
            None,
            None,
            archive_path=archive_result["archive_path"],
        )
        return 0
    event = (
        "archive_blocked"
        if archive_result["state"] == "blocked"
        else "error"
    )
    _emit(
        json_mode,
        event,
        archive_result["task_id"],
        archive_result["message"],
        None,
        None,
    )
    return 1


def _append_batch_receipts(inbox_dir, ready_task_ids, json_mode):
    """Append a REPORT_RECEIVED event for each ready batch report.

    Mirrors the single-report and generic watcher paths so a consolidated batch
    wake leaves the same append-only receipt trail in events.jsonl. Idempotent:
    the event id is keyed on task_id + report mtime via report_event_id(), so a
    re-armed batch (e.g., quorum wakes) never duplicates a receipt. Returns True
    on success, False on a write error (caller should fail closed).
    """
    events_path = os.path.join(inbox_dir, "events.jsonl")
    targets = set(ready_task_ids)
    if not targets or not os.path.isfile(events_path):
        return True
    task_index = _load_task_index(inbox_dir)
    try:
        entries = os.listdir(inbox_dir)
    except OSError:
        return True
    tasks = _scan_tasks(inbox_dir)
    occurred_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for entry in sorted(entries):
        if not entry.endswith(".md"):
            continue
        filepath = os.path.join(inbox_dir, entry)
        if not os.path.isfile(filepath):
            continue
        data, _ = _parse_frontmatter(filepath)
        if not data or data.get("schema") != "agent-file-coordination/report":
            continue
        tid = data.get("task_id", "").strip()
        if tid not in targets:
            continue
        ok, _reasons = _validate_report(filepath, task_index=task_index)
        if not ok:
            continue
        try:
            mtime = _mtime_iso(filepath)
        except OSError:
            continue
        event = {
            "schema": "agent-file-coordination/event",
            "schema_version": "0.1.0",
            "event_id": report_event_id(tid, mtime),
            "event_type": "REPORT_RECEIVED",
            "task_id": tid,
            "agent_name": data.get("agent_name", ""),
            "created_at": occurred_at[:10],
            "report_path": filepath,
            "summary": "Detected schema-valid report {}.".format(entry),
        }
        add_event_context(event, tasks.get(tid, {}), "report_intake", occurred_at)
        try:
            append_event_once(events_path, event)
        except OSError as exc:
            _emit(json_mode, "error", tid,
                  "cannot append REPORT_RECEIVED event: {}".format(exc),
                  filepath, None)
            return False
    return True


def _run_batch_wait(inbox_dir, expected_reports, expected_task_ids,
                    json_mode, max_iterations, poll_interval, stale_threshold,
                    prev_state=None, state_file=None):
    """Block until N schema-valid reports arrive, then return once.

    The waiting and counting happen here in the subprocess (zero coordinator
    tokens); the coordinator gets exactly one consolidated result regardless
    of N, instead of arming the watcher once per worker.

    Stateful: loads and honors .afc-poll-state.json seen-mtimes so that an
    already-consumed report (mtime <= seen) does NOT count again — a re-armed
    full or quorum batch waits for new reports instead of re-firing on a report
    an earlier wake already handled. Updates seen-state monotonically on a
    successful wake.

    A newly-rejected expected task (invalid report, no valid report yet) wakes
    ``report_rejected`` (exit 3) immediately, matching the single/generic paths,
    instead of waiting out the batch. A one-shot staleness alarm still fires: if
    an expected worker stays ASSIGNED with no report past ``stale_threshold``,
    the batch wakes early with ``stale_alarm`` instead of blocking until
    max_iterations.
    """
    if prev_state is None:
        prev_state = {}
    if state_file is None:
        state_file = os.path.join(inbox_dir, ".afc-poll-state.json")
    targets = set(expected_task_ids)
    for iteration in range(max_iterations):
        # Build the task index once per poll pass; reuse for the scan and the
        # reject re-check so the pass stays O(reports + tasks).
        task_index = _load_task_index(inbox_dir)
        report_files = _scan_report_files(inbox_dir)
        # First report file (by sorted name) per in-scope task_id.
        task_report = {}
        for fname, fpath in report_files.items():
            rd, _ = _parse_frontmatter(fpath)
            if not rd:
                continue
            rtid = rd.get("task_id", "").strip()
            if rtid and (not targets or rtid in targets) and rtid not in task_report:
                task_report[rtid] = (fname, fpath)

        valid, rejected = _scan_valid_reports(inbox_dir, task_index=task_index)
        ready_set = valid & targets if targets else valid
        ready = sorted(ready_set)
        bad = sorted(rejected & targets) if targets else sorted(rejected)

        # A newly-rejected EXPECTED task (invalid report and no valid report
        # yet) wakes report_rejected immediately, matching the single/generic
        # paths, instead of silently waiting out the batch. Scoped to an
        # explicit target set so an unrelated malformed file in an unscoped
        # wait does not hijack the batch, and skipped for a task that also has
        # a valid report or whose rejection was already seen.
        if targets:
            for tid in bad:
                if tid in ready_set:
                    continue
                entry = task_report.get(tid)
                if not entry:
                    continue
                fname, fpath = entry
                ok, reasons = _validate_report(fpath, task_index=task_index)
                if ok:
                    continue
                try:
                    cur_mtime = _mtime_iso(fpath)
                except OSError:
                    cur_mtime = ""
                prev_entry = prev_state.get(fname)
                if prev_entry is not None and cur_mtime:
                    prev_mtime = prev_entry.get("mtime", "") if isinstance(prev_entry, dict) else prev_entry
                    prev_status = prev_entry.get("status", "") if isinstance(prev_entry, dict) else "seen"
                    if prev_status == "rejected" and cur_mtime <= prev_mtime:
                        continue
                next_state = dict(prev_state)
                next_state[fname] = {
                    "mtime": cur_mtime,
                    "status": "rejected",
                    "rejection_reasons": reasons,
                }
                if not _save_state(state_file, next_state):
                    # Fail closed, like the valid-report batch path: if the
                    # rejected mtime is not persisted, the next re-arm would see
                    # the same bad report as new and loop on duplicate repair
                    # handling instead of surfacing the persistence error.
                    _emit(json_mode, "error", tid,
                          "cannot persist state to {}: "
                          "os.replace() failed after retries".format(
                              state_file), fpath, None)
                    return 1
                _emit(json_mode, "report_rejected", tid,
                      "report for '{}' failed validation: {}".format(
                          tid, "; ".join(reasons)),
                      fpath, reasons)
                return 3

        # Skip any already-consumed report (mtime <= seen) regardless of task
        # status, so a re-armed full OR quorum batch waits for new reports
        # instead of recounting a report an earlier wake already handled.
        filtered_ready = []
        for tid in ready:
            entry = task_report.get(tid)
            if entry:
                fname, fpath = entry
                prev_entry = prev_state.get(fname)
                if prev_entry is not None:
                    prev_mtime = prev_entry.get("mtime", "") if isinstance(prev_entry, dict) else prev_entry
                    try:
                        cur_mtime = _mtime_iso(fpath)
                    except OSError:
                        cur_mtime = ""
                    if cur_mtime and cur_mtime <= prev_mtime:
                        continue
            filtered_ready.append(tid)

        if len(filtered_ready) >= expected_reports:
            next_state = dict(prev_state)
            for tid in filtered_ready:
                entry = task_report.get(tid)
                if entry:
                    fname, fpath = entry
                    try:
                        next_state[fname] = {
                            "mtime": _mtime_iso(fpath),
                            "status": "valid",
                        }
                    except OSError:
                        pass
            # Append receipts BEFORE marking the reports consumed in state.
            # _append_batch_receipts is idempotent (event_id keyed on
            # task_id + mtime), so if state persistence fails afterwards the
            # next re-arm re-appends the same receipts harmlessly and retries.
            # The reverse order would mark reports consumed (cur_mtime <=
            # prev_mtime) and then lose the wake forever if the receipt write
            # failed, leaving the coordinator with no reports_ready.
            if not _append_batch_receipts(inbox_dir, filtered_ready, json_mode):
                return 1
            if not _save_state(state_file, next_state):
                _emit(json_mode, "error", None,
                      "cannot persist state to {}: "
                      "os.replace() failed after retries".format(
                          state_file), None, None)
                return 1
            _emit(
                json_mode, "reports_ready", None,
                "{} of {} schema-valid reports ready: {}".format(
                    len(filtered_ready), expected_reports,
                    ", ".join(filtered_ready)
                ),
                None, None,
                extra={
                    "expected_reports": expected_reports,
                    "ready_task_ids": filtered_ready,
                    "rejected_task_ids": bad,
                },
            )
            return 0
        # Early staleness alarm (one-shot): a worker that will never report
        # should not force the rest of the batch to block until max_iterations.
        stale_task, age_secs = _find_oldest_stale_task(
            inbox_dir, stale_threshold, expected_task_ids
        )
        if stale_task is not None:
            age_mins = int(age_secs // 60)
            _emit(
                json_mode, "stale_alarm", stale_task,
                "task '{}' ASSIGNED for {} min with no report ({} of {} batch "
                "reports ready)".format(
                    stale_task, age_mins, len(filtered_ready), expected_reports
                ),
                None, None,
                extra={
                    "expected_reports": expected_reports,
                    "ready_task_ids": filtered_ready,
                    "rejected_task_ids": bad,
                },
            )
            return 2
        if iteration < max_iterations - 1:
            time.sleep(poll_interval)
    valid, rejected = _scan_valid_reports(inbox_dir)
    ready = sorted(valid & targets) if targets else sorted(valid)
    bad = sorted(rejected & targets) if targets else sorted(rejected)
    _emit(
        json_mode, "reports_incomplete", None,
        "only {} of {} schema-valid reports arrived before timeout".format(
            len(ready), expected_reports
        ),
        None, None,
        extra={
            "expected_reports": expected_reports,
            "ready_task_ids": ready,
            "rejected_task_ids": bad,
        },
    )
    return 2


def _run_expected_report_watch(inbox_dir, expected_report_path,
                               expected_report_filename, expected_task_ids,
                               prev_state, state_file, json_mode, auto_archive,
                               max_iterations, poll_interval):
    """Watch for one expected report file (inbox-relative)."""
    for iteration in range(max_iterations):
        if auto_archive:
            rc = _check_auto_archive(inbox_dir, json_mode)
            if rc is not None:
                return rc

        # --- Expected-report mode: only process the one expected file ---
        if not os.path.isfile(expected_report_path):
            # File not found — keep polling (may arrive later)
            if iteration < max_iterations - 1:
                time.sleep(poll_interval)
            continue

        try:
            mtime = _mtime_iso(expected_report_path)
        except OSError:
            if iteration < max_iterations - 1:
                time.sleep(poll_interval)
            continue

        # Check state: already seen at this mtime?
        prev_entry = prev_state.get(expected_report_filename)
        if prev_entry is not None:
            prev_mtime = prev_entry.get("mtime", "") if isinstance(prev_entry, dict) else prev_entry
            prev_status = prev_entry.get("status", "") if isinstance(prev_entry, dict) else "seen"
            if mtime <= prev_mtime:
                expected_task_id = expected_task_ids[0] if expected_task_ids else ""
                task_status = ""
                if expected_task_id:
                    task_status = _scan_tasks(inbox_dir).get(
                        expected_task_id, {}
                    ).get("status", "")
                if task_status == "NEEDS_FIX":
                    if iteration < max_iterations - 1:
                        time.sleep(poll_interval)
                    continue
                # Already seen. If previously rejected, no re-wake.
                if prev_status == "rejected":
                    _emit(json_mode, "no_wake", None,
                          "expected report {} already rejected at this mtime".format(
                              expected_report_filename), None, None)
                    return 0
                # Previously valid — also no re-wake
                _emit(json_mode, "no_wake", None,
                      "expected report {} already consumed".format(
                          expected_report_filename), None, None)
                return 0

        # File exists and is new/updated — validate.
        # Structured parse keeps list-block fields (evidence_refs etc.) as
        # real lists, matching the canonical validator contract.
        report_data, report_body, parse_errs = extract_structured_frontmatter(expected_report_path)
        parse_err = "; ".join(parse_errs) if parse_errs else ""

        # Check: must have report schema frontmatter
        if parse_err or not report_data:
            if parse_err:
                reasons = ["parse error: {}".format(parse_err)]
            else:
                reasons = ["no frontmatter" if report_data is None else "empty frontmatter"]
            _reject_expected(
                json_mode, expected_report_path, expected_report_filename,
                mtime, reasons, prev_state, state_file, inbox_dir,
            )
            return 3

        if report_data.get("schema") != "agent-file-coordination/report":
            reasons = ["wrong schema: {}".format(report_data.get("schema"))]
            _reject_expected(
                json_mode, expected_report_path, expected_report_filename,
                mtime, reasons, prev_state, state_file, inbox_dir,
            )
            return 3

        # Cross-check: expected-task-id
        report_task_id = report_data.get("task_id", "").strip()
        expected_task_id = expected_task_ids[0] if expected_task_ids else ""
        if expected_task_id and report_task_id != expected_task_id:
            reasons = ["task_id mismatch: expected '{}', got '{}'".format(
                expected_task_id, report_task_id)]
            _reject_expected(
                json_mode, expected_report_path, expected_report_filename,
                mtime, reasons, prev_state, state_file, inbox_dir,
            )
            return 3

        # Full schema validation. Pass the matching task's full frontmatter so
        # the same cross-checks intake runs (agent_name / coordination_mode /
        # comparison_group / modify_source) reject here too.
        task_for_check = _load_task_data_for_report(inbox_dir, report_data)
        is_valid, reasons = validate_report_schema(
            report_data, body=report_body, task=task_for_check
        )
        if not is_valid:
            _reject_expected(
                json_mode, expected_report_path, expected_report_filename,
                mtime, reasons, prev_state, state_file, inbox_dir,
            )
            return 3

        # Valid! Update state (only for this one file) and emit report_ready.
        next_state = dict(prev_state)
        next_state[expected_report_filename] = {"mtime": mtime, "status": "valid"}
        if not _save_state(state_file, next_state):
            _emit(json_mode, "error", None,
                  "cannot persist state", None, None)
            return 1

        # Emit REPORT_RECEIVED event
        occurred_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        task_data = _scan_tasks(inbox_dir).get(report_task_id, {})
        event = {
            "schema": "agent-file-coordination/event",
            "schema_version": "0.1.0",
            "event_id": report_event_id(report_task_id, mtime),
            "event_type": "REPORT_RECEIVED",
            "task_id": report_task_id,
            "agent_name": report_data.get("agent_name", ""),
            "created_at": occurred_at[:10],
            "report_path": expected_report_path,
            "summary": "Detected schema-valid report {}.".format(
                expected_report_filename),
        }
        add_event_context(event, task_data, "report_intake", occurred_at)
        events_path = os.path.join(inbox_dir, "events.jsonl")
        if os.path.isfile(events_path):
            try:
                append_event_once(events_path, event)
            except OSError:
                pass  # non-fatal

        _emit(json_mode, "report_ready", report_task_id,
              "new schema-valid report: {}".format(expected_report_filename),
              expected_report_path, None)
        return 0

    _emit(json_mode, "no_wake", None,
          "no wake event after {} iterations".format(max_iterations), None, None)
    return 0


def _run_generic_watch(inbox_dir, expected_task_ids, prev_state, state_file,
                       json_mode, auto_archive, stale_threshold,
                       max_iterations, poll_interval):
    """Scan all reports each iteration (original CAL-2 behavior)."""
    for iteration in range(max_iterations):
        if auto_archive:
            rc = _check_auto_archive(inbox_dir, json_mode)
            if rc is not None:
                return rc

        # --- Generic mode: scan all reports (original CAL-2 behavior) ---
        try:
            current_reports = _scan_report_files(inbox_dir)
        except OSError as exc:
            _emit(json_mode, "error", None,
                  "cannot scan inbox: {}".format(exc), None, None)
            return 1

        current_state = {}
        new_report = None
        rejected_report = None
        ready_reports = []
        rejected_reports = []
        # Build the task index once per poll pass for cross-checks.
        task_index = _load_task_index(inbox_dir)

        for filename in sorted(current_reports.keys()):
            filepath = current_reports[filename]
            try:
                mtime = _mtime_iso(filepath)
            except OSError:
                continue

            report_data, _ = _parse_frontmatter(filepath)
            report_task_id = ""
            if report_data:
                report_task_id = report_data.get("task_id", "").strip()
            if expected_task_ids and report_task_id not in expected_task_ids:
                continue

            prev_entry = prev_state.get(filename)
            if prev_entry is not None:
                prev_mtime = prev_entry.get("mtime", "") if isinstance(prev_entry, dict) else prev_entry
                if mtime <= prev_mtime:
                    current_state[filename] = prev_entry if isinstance(prev_entry, dict) else {"mtime": prev_mtime, "status": "seen"}
                    continue

            is_valid, reasons = _validate_report(filepath, task_index=task_index)
            if is_valid:
                report_info = {
                    "filename": filename,
                    "path": filepath,
                    "mtime": mtime,
                    "data": report_data or {},
                    "task_id": report_task_id,
                }
                ready_reports.append(report_info)
                if new_report is None:
                    current_state[filename] = {"mtime": mtime, "status": "valid"}
                    new_report = report_info
            else:
                report_info = {
                    "filename": filename,
                    "path": filepath,
                    "mtime": mtime,
                    "data": report_data or {},
                    "task_id": report_task_id,
                    "reasons": reasons,
                }
                rejected_reports.append(report_info)
                if new_report is None:
                    current_state[filename] = {
                        "mtime": mtime,
                        "status": "rejected",
                        "rejection_reasons": reasons,
                    }
                print(
                    "watch: rejected report {}: {}".format(
                        filename, "; ".join(reasons)
                    ),
                    file=sys.stderr,
                )
                if rejected_report is None:
                    rejected_report = report_info

        # Determine what to emit. Priority: valid report > rejected report.
        if new_report is not None:
            # --- Valid report found ---
            occurred_at = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            task_id = new_report["task_id"]
            task_data = _scan_tasks(inbox_dir).get(task_id, {})
            event = {
                "schema": "agent-file-coordination/event",
                "schema_version": "0.1.0",
                "event_id": report_event_id(task_id, new_report["mtime"]),
                "event_type": "REPORT_RECEIVED",
                "task_id": task_id,
                "agent_name": new_report["data"].get("agent_name", ""),
                "created_at": occurred_at[:10],
                "report_path": new_report["path"],
                "summary": "Detected schema-valid report {}.".format(
                    new_report["filename"]
                ),
            }
            add_event_context(
                event, task_data, "report_intake", occurred_at
            )
            events_path = os.path.join(inbox_dir, "events.jsonl")
            if os.path.isfile(events_path):
                try:
                    append_event_once(events_path, event)
                except OSError as exc:
                    _emit(
                        json_mode, "error", task_id,
                        "cannot append REPORT_RECEIVED event: {}".format(exc),
                        new_report["path"], None,
                    )
                    return 1

            next_state = dict(prev_state)
            next_state.update(current_state)
            if not _save_state(state_file, next_state):
                _emit(json_mode, "error", None,
                      "cannot persist state to {}: "
                      "os.replace() failed after retries".format(
                          state_file), None, None)
                return 1

            extra = _wake_extra(
                ready_reports,
                rejected_reports,
                (
                    "intake ready report, then re-arm for pending reports"
                    if len(ready_reports) > 1 or rejected_reports
                    else ""
                ),
            )
            _emit(json_mode, "report_ready", task_id,
                  "new schema-valid report: {}".format(
                      new_report["filename"]),
                  new_report["path"], None, extra=extra)
            return 0

        if rejected_report is not None:
            # --- Rejected report found ---
            occurred_at = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            task_id = rejected_report["task_id"]
            reasons_text = "; ".join(rejected_report["reasons"])

            event = {
                "schema": "agent-file-coordination/event",
                "schema_version": "0.1.0",
                "event_id": "REPORT_REJECTED-{}-{}".format(
                    task_id or "unknown", rejected_report["mtime"]
                ),
                "event_type": "REPORT_REJECTED",
                "task_id": task_id,
                "agent_name": rejected_report["data"].get("agent_name", ""),
                "created_at": occurred_at[:10],
                "report_path": rejected_report["path"],
                "summary": "Report rejected during watcher intake: {}".format(
                    reasons_text
                ),
            }
            if task_id:
                task_data = _scan_tasks(inbox_dir).get(task_id, {})
                add_event_context(event, task_data, "report_intake", occurred_at)
            else:
                event["occurred_at"] = occurred_at
                event["phase"] = "report_intake"

            events_path = os.path.join(inbox_dir, "events.jsonl")
            if os.path.isfile(events_path):
                try:
                    append_event_once(events_path, event)
                except OSError as exc:
                    _emit(
                        json_mode, "error", task_id,
                        "cannot append REPORT_REJECTED event: {}".format(exc),
                        rejected_report["path"], None,
                    )
                    return 1

            next_state = dict(prev_state)
            next_state.update(current_state)
            if not _save_state(state_file, next_state):
                _emit(json_mode, "error", None,
                      "cannot persist state to {}: "
                      "os.replace() failed after retries".format(
                          state_file), None, None)
                return 1

            extra = _wake_extra(
                ready_reports,
                rejected_reports,
                "repair rejected report, then re-arm if task remains active",
            )
            _emit(json_mode, "report_rejected", task_id,
                  "{} rejected: {}".format(
                      rejected_report["filename"], reasons_text),
                  rejected_report["path"],
                  rejected_report["reasons"], extra=extra)
            return 3

        # No new or rejected reports
        if current_state:
            next_state = dict(prev_state)
            next_state.update(current_state)
            _save_state(state_file, next_state)

        # --- Check for staleness (one-shot) ---
        stale_task, age_secs = _find_oldest_stale_task(
            inbox_dir, stale_threshold, expected_task_ids
        )
        if stale_task is not None:
            age_mins = int(age_secs // 60)
            _emit(json_mode, "stale_alarm", stale_task,
                  "task '{}' ASSIGNED for {} min with no report".format(
                      stale_task, age_mins),
                  None, None)
            return 2

        # --- No wake event this iteration; wait ---
        if iteration < max_iterations - 1:
            time.sleep(poll_interval)

    # Max iterations reached — exit without waking
    _emit(json_mode, "no_wake", None,
          "no wake event after {} iterations".format(max_iterations), None, None)
    return 0


def main():
    opts, code = parse_args(sys.argv[1:])
    if code is not None:
        return code
    stale_threshold = opts.stale_threshold
    poll_interval = opts.poll_interval
    max_iterations = opts.max_iterations
    json_mode = opts.json_mode
    expected_task_ids = opts.expected_task_ids
    expected_reports = opts.expected_reports
    auto_archive = opts.auto_archive
    inbox_dir = opts.inbox_dir
    expected_report_path = opts.expected_report_path
    expected_report_filename = opts.expected_report_filename

    # State file location (same convention as afc-poll.py)
    state_file = os.path.join(inbox_dir, ".afc-poll-state.json")

    # Clean up our own stale temp files from an interrupted prior write (CAL-2
    # hardening: no stale .tmp after persistence). Scope to our fixed names —
    # afc-report.py / afc-assign.py write in-flight mkstemp temps in this same
    # inbox, and a blanket *.tmp sweep could unlink a producer's live temp and
    # make its os.replace fail, losing a report.
    sweep_stale_tmp(inbox_dir, names=(".afc-poll-state.json.tmp", "STATUS.md.tmp"))

    # Load existing state (with backward-compatible migration)
    try:
        prev_state = _load_state(state_file)
    except ValueError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1

    # Batch mode: block until N schema-valid reports arrive, return once.
    # Pass state for NEEDS_FIX awareness and seen-mtime tracking.
    if expected_reports is not None:
        return _run_batch_wait(
            inbox_dir, expected_reports, expected_task_ids,
            json_mode, max_iterations, poll_interval, stale_threshold,
            prev_state=prev_state, state_file=state_file,
        )

    # Dispatch to the mode-specific watch loop.
    if expected_report_path is not None:
        return _run_expected_report_watch(
            inbox_dir, expected_report_path, expected_report_filename,
            expected_task_ids, prev_state, state_file, json_mode,
            auto_archive, max_iterations, poll_interval,
        )
    return _run_generic_watch(
        inbox_dir, expected_task_ids, prev_state, state_file,
        json_mode, auto_archive, stale_threshold,
        max_iterations, poll_interval,
    )


def _emit(json_mode, event, task_id, message, report_path, rejection_reasons,
          archive_path=None, extra=None):
    """Emit a single wake event line."""
    ts = datetime.now(timezone.utc).strftime("%H:%M")
    if json_mode:
        obj = {
            "event": event,
            "timestamp_utc": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "message": message,
        }
        if task_id:
            obj["task_id"] = task_id
        if report_path:
            obj["report_path"] = report_path
        if archive_path:
            obj["archive_path"] = archive_path
        if rejection_reasons:
            obj["rejection_reasons"] = rejection_reasons
        if extra:
            obj.update(extra)
        print(json.dumps(obj, ensure_ascii=False))
    else:
        if task_id:
            print("[{}] {}: {}".format(ts, event, message))
        else:
            print("[{}] {}: {}".format(ts, event, message))


if __name__ == "__main__":
    sys.exit(main())
