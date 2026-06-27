#!/usr/bin/env python3
"""Print the next bounded coordinator action from an agent-inbox directory.

Reads active coordination state from task and report files and recommends the
single next coordinator action. This is a read-only, one-step command: it
never modifies files, rewrites state, or appends events unless --refresh-status
is given explicitly.

Python stdlib only. Python 3.8+ compatible. Windows + POSIX safe.

Decision order (first matching rule wins):
  1. Malformed inbox state, duplicate task IDs, duplicate reports, orphan
     reports, or unknown active status -> FAIL (exit 1)
  2. Report exists for an active task -> RECOMMEND_REVIEW
  3. Task in REPORTED or REVIEWING without a report file -> FAIL (exit 1,
     inconsistent state: report-expected status but no report on disk)
  4. Task in DRAFT -> RECOMMEND_ASSIGN
  5. Task in ASSIGNED or RUNNING with no report -> RECOMMEND_WAIT
  6. Task in NEEDS_FIX -> RECOMMEND_REPAIR_REVIEW
  7. No active task -> NO_ACTION

Coordinator thread-pressure override (optional, --context-pct):
  The inbox decision above is about the inbox; it cannot see how large the
  coordinator's own thread has grown. The biggest measured Codex quota sink is
  an overgrown coordinator thread that re-feeds its context every turn. When
  the coordinator self-reports its current context window usage with
  --context-pct, this script turns the advisory thresholds in
  docs/CACHE_HYGIENE.md into a deterministic verdict:

    * context-pct >= --handoff-pct (default 80) -> action becomes
      RECOMMEND_HANDOFF (preempts every inbox action except FAIL): write a
      new-thread handoff (scripts/afc-handoff.py) and continue in a fresh
      thread before doing more work.
    * --compact-pct (default 50) <= context-pct < --handoff-pct -> the inbox
      action is unchanged but an `advisory` line recommends compaction first.

  Without --context-pct the output is byte-identical to the inbox-only
  behavior; the override never invents a percentage on its own.

Usage:
    python -B scripts/afc-next.py [--json] [--refresh-status]
        [--context-pct N] [--handoff-pct N] [--compact-pct N] <INBOX_DIR>

Exit codes:
    0   success (action, handoff recommendation, or no-action determined)
    1   validation failure (malformed inbox, duplicates, orphans, unknown
        state, or an out-of-range --context-pct / threshold value)
"""

import json
import os
import subprocess
import sys

from afc_frontmatter import parse_frontmatter_flat as parse_frontmatter


ACTIVE_STATES = frozenset([
    "DRAFT", "ASSIGNED", "RUNNING", "REPORTED",
    "REVIEWING", "NEEDS_FIX", "BLOCKED",
])

CLOSED_STATES = frozenset([
    "CLOSED_GO", "CLOSED_PARTIAL", "CLOSED_RED",
    "CANCELLED", "SUPERSEDED",
])

ALL_KNOWN_STATES = ACTIVE_STATES | CLOSED_STATES

# Coordinator thread-pressure thresholds (percent of context window).
# These mirror the advisory rules in docs/CACHE_HYGIENE.md
# (>50% compress, >80% new-thread handoff).
DEFAULT_HANDOFF_PCT = 80.0
DEFAULT_COMPACT_PCT = 50.0


def parse_pct(raw, flag):
    """Parse a 0-100 percentage value for a flag. Returns (value, error)."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, f"{flag} requires a number between 0 and 100, got {raw!r}"
    if value < 0 or value > 100:
        return None, f"{flag} must be between 0 and 100, got {raw}"
    return value, None


def fmt_pct(value):
    """Format a percentage without a trailing .0 for whole numbers."""
    if value == int(value):
        return str(int(value))
    return ("%g" % value)


def _find_afc_status():
    """Locate afc-status.py relative to this script."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "afc-status.py")
    if os.path.isfile(path):
        return path
    return None


def scan_inbox(inbox_dir):
    """Scan an inbox directory for task and report files.

    Returns (tasks, reports, errors) where:
      tasks: dict of task_id -> {task_id, agent_name, role, status,
             report_path, workspace_path, filepath}
      reports: dict of task_id -> {task_id, agent_name, filepath}
      errors: list of error strings

    Fails closed on: missing task_id, duplicate task IDs, duplicate reports,
    orphan reports, unknown active states.
    """
    tasks = {}
    reports = {}
    errors = []

    try:
        entries = os.listdir(inbox_dir)
    except OSError as exc:
        return tasks, reports, [f"cannot list {inbox_dir}: {exc}"]

    for entry in sorted(entries):
        if not entry.endswith(".md"):
            continue
        filepath = os.path.join(inbox_dir, entry)
        if not os.path.isfile(filepath):
            continue

        data, err = parse_frontmatter(filepath)
        if err:
            errors.append(err)
            continue

        schema = data.get("schema", "")

        if schema == "agent-file-coordination/task":
            task_id = data.get("task_id", "").strip()
            if not task_id:
                errors.append(f"task file missing task_id: {filepath}")
                continue
            if task_id in tasks:
                errors.append(
                    f"duplicate task_id '{task_id}' in "
                    f"{tasks[task_id]['filepath']} and {filepath}"
                )
                continue

            missing_fields = [
                field
                for field in ("task_id", "agent_name", "role", "status")
                if not data.get(field)
            ]
            if missing_fields:
                errors.extend(
                    "task {} missing required field '{}'".format(
                        task_id, field
                    )
                    for field in missing_fields
                )
                continue

            status = data.get("status", "").strip().upper()
            workspace_path = data.get("workspace.path", "")
            report_path = data.get("report_path", "")

            # Validate status: fail on unknown states in active set
            if status not in ALL_KNOWN_STATES:
                errors.append(
                    f"task {task_id} has unknown status '{status}' in {filepath}"
                )

            tasks[task_id] = {
                "task_id": task_id,
                "agent_name": data.get("agent_name", ""),
                "role": data.get("role", ""),
                "status": status,
                "report_path": report_path,
                "workspace_path": workspace_path,
                "filepath": filepath,
            }

        elif schema == "agent-file-coordination/report":
            task_id = data.get("task_id", "").strip()
            if not task_id:
                errors.append(f"report file missing task_id: {filepath}")
                continue
            if task_id in reports:
                errors.append(
                    f"duplicate report for task_id '{task_id}': "
                    f"{reports[task_id]['filepath']} and {filepath}"
                )
                continue

            reports[task_id] = {
                "task_id": task_id,
                "agent_name": data.get("agent_name", ""),
                "filepath": filepath,
            }

    # Check for orphan reports
    for task_id, info in reports.items():
        if task_id not in tasks:
            errors.append(
                f"orphan report for unknown task_id '{task_id}': {info['filepath']}"
            )

    return tasks, reports, errors


def decide_next_action(tasks, reports):
    """Determine the single next coordinator action from inbox state.

    Applies the decision order from the module docstring. The decision
    procedure is priority-ordered across all active tasks: rule 2 is checked
    for ALL tasks before rule 3, rule 3 for ALL tasks before rule 4, etc.
    Within the same rule, tasks are ordered by task_id for determinism.

    Returns (action, task_id, reason) where action is one of:
      RECOMMEND_REVIEW, RECOMMEND_ASSIGN, RECOMMEND_WAIT,
      RECOMMEND_REPAIR_REVIEW, NO_ACTION
    """
    # Collect active tasks (non-closed states)
    active_tasks = {
        tid: t for tid, t in tasks.items()
        if t["status"] in ACTIVE_STATES
    }

    if not active_tasks:
        return "NO_ACTION", None, "no active tasks"

    # Decision order: check each rule across ALL active tasks before
    # falling through to the next rule. Within a rule, sort by task_id
    # for determinism.

    # Rule 2: report exists for an active task -> RECOMMEND_REVIEW
    for task_id in sorted(active_tasks.keys()):
        task = active_tasks[task_id]
        if task_id in reports:
            return (
                "RECOMMEND_REVIEW", task_id,
                f"report exists for task '{task_id}' (status: {task['status']}) — "
                f"coordinator should review"
            )

    # Rule 3: REPORTED / REVIEWING without a report -> fail closed
    for task_id in sorted(active_tasks.keys()):
        task = active_tasks[task_id]
        if task["status"] in ("REPORTED", "REVIEWING") and task_id not in reports:
            return (
                "FAIL", task_id,
                f"inconsistent state: task '{task_id}' is {task['status']} "
                f"but no report file found — coordinator must investigate"
            )

    # Rule 4: DRAFT -> RECOMMEND_ASSIGN
    for task_id in sorted(active_tasks.keys()):
        task = active_tasks[task_id]
        if task["status"] == "DRAFT":
            return (
                "RECOMMEND_ASSIGN", task_id,
                f"task '{task_id}' is DRAFT — coordinator should assign a worker"
            )

    # Rule 5: ASSIGNED / RUNNING with no report -> RECOMMEND_WAIT
    for task_id in sorted(active_tasks.keys()):
        task = active_tasks[task_id]
        if task["status"] in ("ASSIGNED", "RUNNING"):
            return (
                "RECOMMEND_WAIT", task_id,
                f"task '{task_id}' is {task['status']} with no report — "
                f"wait for worker or check progress"
            )

    # Rule 6: NEEDS_FIX -> RECOMMEND_REPAIR_REVIEW
    for task_id in sorted(active_tasks.keys()):
        task = active_tasks[task_id]
        if task["status"] == "NEEDS_FIX":
            return (
                "RECOMMEND_REPAIR_REVIEW", task_id,
                f"task '{task_id}' is NEEDS_FIX — "
                f"coordinator should review repair without automatic worker retry"
            )

    # Rule 7: no actionable active task (e.g., all BLOCKED)
    return "NO_ACTION", None, "no actionable active tasks"


def main():
    args = sys.argv[1:]
    json_mode = False
    refresh_status = False
    context_pct = None
    handoff_pct = DEFAULT_HANDOFF_PCT
    compact_pct = DEFAULT_COMPACT_PCT
    positional = []

    i = 0
    while i < len(args):
        if args[i] == "--json":
            json_mode = True
        elif args[i] == "--refresh-status":
            refresh_status = True
        elif args[i] in ("--context-pct", "--handoff-pct", "--compact-pct"):
            flag = args[i]
            if i + 1 >= len(args):
                print(f"error: {flag} requires a value", file=sys.stderr)
                return 1
            value, err = parse_pct(args[i + 1], flag)
            if err:
                print(f"error: {err}", file=sys.stderr)
                return 1
            if flag == "--context-pct":
                context_pct = value
            elif flag == "--handoff-pct":
                handoff_pct = value
            else:
                compact_pct = value
            i += 1
        elif args[i] == "--help" or args[i] == "-h":
            print(
                "afc-next.py - print the next bounded coordinator action.\n"
                "\n"
                "Reads an .agent-inbox directory and prints the next\n"
                "coordinator action from existing task/report/status state.\n"
                "Default behavior is read-only: no status rewrite, no state\n"
                "file write, no event append.\n"
                "\n"
                "Decision order (first matching rule wins):\n"
                "  1. Malformed state / duplicates / orphans / unknown status -> FAIL\n"
                "  2. Report exists for active task -> RECOMMEND_REVIEW\n"
                "  3. REPORTED/REVIEWING without report -> FAIL (inconsistent)\n"
                "  4. DRAFT task -> RECOMMEND_ASSIGN\n"
                "  5. ASSIGNED/RUNNING with no report -> RECOMMEND_WAIT\n"
                "  6. NEEDS_FIX -> RECOMMEND_REPAIR_REVIEW\n"
                "  7. No active task -> NO_ACTION\n"
                "\n"
                "Coordinator thread-pressure override (optional):\n"
                "  --context-pct N   coordinator's current context-window usage (0-100)\n"
                "  --handoff-pct N   handoff threshold (default 80): >= -> RECOMMEND_HANDOFF\n"
                "  --compact-pct N   compact threshold (default 50): >= -> advisory line\n"
                "  FAIL still preempts a handoff recommendation. Without --context-pct\n"
                "  the output is byte-identical to inbox-only behavior.\n"
                "\n"
                "Usage:\n"
                "    python -B scripts/afc-next.py [--json] [--refresh-status]\n"
                "        [--context-pct N] [--handoff-pct N] [--compact-pct N] <INBOX_DIR>"
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
            "usage: python -B scripts/afc-next.py [--json] [--refresh-status] <INBOX_DIR>",
            file=sys.stderr,
        )
        return 1

    inbox_dir = positional[0]

    if not os.path.isdir(inbox_dir):
        print(f"error: directory not found: {inbox_dir}", file=sys.stderr)
        return 1

    # Step 1: Optionally refresh STATUS.md via afc-status.py
    if refresh_status:
        afc_status = _find_afc_status()
        if afc_status is None:
            print(
                "error: afc-status.py not found alongside this script",
                file=sys.stderr,
            )
            return 1
        cmd = [sys.executable, "-B", afc_status, inbox_dir]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            print(
                f"error: afc-status.py failed (exit {result.returncode}): {stderr}",
                file=sys.stderr,
            )
            return 1

    # Step 2: Scan inbox
    tasks, reports, errors = scan_inbox(inbox_dir)

    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        return 1

    # Step 3: Decide next action
    action, task_id, reason = decide_next_action(tasks, reports)

    # Step 3b: Coordinator thread-pressure override. FAIL (inconsistent inbox
    # state) is never overridden — broken state must be fixed before a handoff.
    advisory = None
    if context_pct is not None and action != "FAIL":
        if context_pct >= handoff_pct:
            action = "RECOMMEND_HANDOFF"
            task_id = None
            reason = (
                f"coordinator context at {fmt_pct(context_pct)}% "
                f"(>= {fmt_pct(handoff_pct)}% handoff threshold) — write a "
                f"new-thread handoff (scripts/afc-handoff.py) and continue in a "
                f"fresh thread before doing more coordinator work"
            )
        elif context_pct >= compact_pct:
            advisory = (
                f"coordinator context at {fmt_pct(context_pct)}% "
                f"(>= {fmt_pct(compact_pct)}% compact threshold) — compress or "
                f"summarize the thread before the next coordinator turn"
            )

    # Step 4: Output
    is_fail = action == "FAIL"

    if json_mode:
        output = {
            "action": action,
            "task_id": task_id,
            "reason": reason,
            "active_tasks": len([
                t for t in tasks.values() if t["status"] in ACTIVE_STATES
            ]),
            "total_tasks": len(tasks),
        }
        if context_pct is not None:
            output["context_pct"] = context_pct
            output["advisory"] = advisory
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print(f"action: {action}")
        if task_id:
            print(f"task_id: {task_id}")
        print(f"reason: {reason}")
        if advisory:
            print(f"advisory: {advisory}")

    return 1 if is_fail else 0


if __name__ == "__main__":
    sys.exit(main())
