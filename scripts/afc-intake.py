#!/usr/bin/env python3
"""Batch report intake: one command for schema, budget, Git, base, and scope."""

import argparse
import copy
import json
import os
import re
import subprocess
import sys

from afc_event import append_event_once
from afc_frontmatter import parse_frontmatter_structured as parse_frontmatter
from afc_inbox_validation import format_validation_result, validate_paths
from afc_routing import MAX_EXPECTED_ROUNDS
from afc_constants import (
    CLOSED_STATUSES,
    REPORT_BUDGET_BYTES,
    REVIEW_REPORT_BUDGET_BYTES,
)

REPAIR_HINTS = {
    "REPORT_MISSING": "write the declared report_path with afc-report.py",
    "REPORT_SCHEMA_INVALID_AT_DECLARED_PATH": (
        "regenerate the declared report_path with afc-report.py"
    ),
    "REPORT_OVER_BUDGET": "shorten the report and regenerate it with afc-report.py",
    "TASK_CONTRACT_INVALID": "fix the task frontmatter/schema before intake",
    "REPORT_SCHEMA_INVALID": "regenerate the report with afc-report.py",
    "TASK_REPORT_CONSISTENCY_FAILED": "make report task_id/agent/path match the task",
    "OUT_OF_SCOPE_CHANGES": "remove or report files outside locked_files_or_areas",
    "WORKSPACE_MISSING": "open or restore the declared workspace path",
    "NOT_A_GIT_WORKSPACE": "use the declared Git worktree as workspace",
    "GIT_STATUS_FAILED": "fix Git status errors before intake",
    "BRANCH_MISMATCH": "return the worktree to the task branch or report blocker",
    "BASE_MISMATCH": "rebase/reset only with coordinator approval, otherwise report blocker",
    "VALIDATION_COMMAND_FAILED": (
        "the task validation_command failed on the worker's diff; fix the code "
        "(not the report) and re-run it"
    ),
}

# Wall-clock ceiling for a coordinator-side validation_command re-run.
VALIDATION_COMMAND_TIMEOUT_SECS = 600

# Validation tiers heavy enough that the coordinator re-verifies the worker's
# code first-hand instead of trusting the pasted evidence.
REVERIFY_TIERS = {"full-suite", "production-replay"}


def should_reverify(data):
    """Deterministic risk gate for coordinator-side code re-verification.

    Derived only from fields the coordinator already set in the task contract,
    so the decision is scriptable and never an inflatable LLM "risk score".
    Re-run only for release operations or the heaviest declared tiers; every
    other task trusts the worker's self-run evidence.
    """
    permission_scope = data.get("permission_scope")
    permission_scope = permission_scope if isinstance(permission_scope, dict) else {}
    commit_push = str(permission_scope.get("commit_push") or "").strip().lower()
    tier = str(data.get("validation_tier") or "").strip().lower()
    return commit_push == "approved" or tier in REVERIFY_TIERS


# Structural destructive patterns: these only appear as real shell constructs
# (with spaces, parens, operators, =), never as a substring inside a legitimate
# path or argument, so a raw substring match is safe and never false-positives.
# Bare command words (shutdown, reboot, mkfs) are deliberately NOT here: they
# collide with legitimate test names / selectors (tests/test_shutdown.py,
# pytest -k reboot) and distinguishing command-position from argument-position
# requires a shell parser. The structural patterns below cover the genuinely
# destructive shapes that a coordinator-authored code gate would never contain.
DANGEROUS_VALIDATION_STRUCTURAL = (
    "rm -rf",
    "rm -fr",
    ":(){",            # fork bomb
    ">/dev/sd",
    "dd if=",
)

# Reject output redirection that escapes the workspace (absolute paths or `..`).
# Redirecting to a workspace-relative file like `pytest > log.txt` is legitimate
# for a code gate; redirecting outside the workspace is not.
_REDIRECT_RE = re.compile(r"(?:>>?)\s*([^\s&|;]+)")


def _redirects_outside_workspace(command, cwd):
    """Return a redirect target token if it escapes the workspace, else None.

    Normalizes the target against cwd so disguised escapes like `./../x` or
    `logs/../../x` are caught, not just bare `..` or absolute paths. Shell-
    expanded tokens (`~`, `$VAR`, `${VAR}`) are rejected outright: their final
    location depends on the shell environment and cannot be checked here."""
    cwd_abs = os.path.abspath(cwd)
    for match in _REDIRECT_RE.finditer(command):
        target = match.group(1).strip("'\"")
        # Shell expansion makes the landing site unknowable from Python; reject.
        if "~" in target or "$" in target:
            return target
        resolved = os.path.abspath(os.path.join(cwd_abs, target))
        # resolved must stay within cwd (commonpath handles trailing-sep edge cases).
        try:
            common = os.path.commonpath([cwd_abs, resolved])
        except ValueError:
            common = ""
        if common != cwd_abs:
            return target
    return None


def _reject_dangerous_validation(command, cwd):
    """Return a reason string if the command is too dangerous to execute, else None."""
    if not command:
        return None
    compact = " ".join(command.split()).lower()
    # Only structural patterns: these cannot appear in a legitimate path or
    # argument, so substring matching is exact with no false positives.
    for pattern in DANGEROUS_VALIDATION_STRUCTURAL:
        if pattern in compact:
            return "destructive pattern {!r}".format(pattern)
    escaped = _redirects_outside_workspace(command, cwd)
    if escaped:
        return "output redirect escapes workspace: {!r}".format(escaped)
    return None


def run_validation_command(command, cwd):
    """Run the task's validation_command in the workspace. Returns (rc, tail).

    Threat model: the command originates from the coordinator-authored task
    contract. Workers cannot write task files by protocol convention (not OS
    enforcement), so the command is treated as trusted input run on the
    coordinator's own machine with `shell=True`. Residual risk: if that
    convention is ever violated, an attacker-controlled string would execute
    with the coordinator's privileges. Mitigation: this is inline-injection
    containment, NOT a sandbox. Compound gates (`ruff && pytest`, `pytest |
    tail`) are allowed because a wrapper script could contain everything a
    chain can, so blocking chains only moves danger out of sight. What IS
    blocked is a small literal blocklist of destructive shapes (`rm -rf`,
    fork bomb, `mkfs`, `dd if=`, ...) and output redirects that escape the
    workspace. The trust root remains the task contract.
    """
    rejection = _reject_dangerous_validation(command, cwd)
    if rejection:
        return 127, "validation_command rejected: {}".format(rejection)
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=VALIDATION_COMMAND_TIMEOUT_SECS,
        )
    except subprocess.TimeoutExpired:
        return 124, "validation_command timed out after {}s".format(
            VALIDATION_COMMAND_TIMEOUT_SECS
        )
    except OSError as exc:
        return 127, "validation_command could not run: {}".format(exc)
    tail = ((result.stdout or "") + (result.stderr or "")).strip()
    if len(tail) > 1000:
        tail = "..." + tail[-1000:]
    return result.returncode, tail


def count_repair_rounds(events_path, task_id):
    """Count REPAIR_ROUND marker events for a given task_id in events.jsonl."""
    count = 0
    if not os.path.isfile(events_path):
        return 0
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
                    event.get("event_type") == "REPAIR_ROUND"
                    and event.get("task_id") == task_id
                ):
                    count += 1
    except OSError:
        pass
    return count


def append_repair_round_event(events_path, task_id, created_at, report_mtime=""):
    """Append a REPAIR_ROUND marker event, idempotent on event_id.

    The event_id encodes the report's mtime, so each new report version (each
    real repair attempt) gets its own event. Re-running intake over the same
    report produces the same event_id and does NOT append a duplicate.

    Returns True if a new event was appended, False if already present.
    """
    compact_mtime = "".join(ch for ch in report_mtime if ch.isalnum())
    event = {
        "schema": "agent-file-coordination/event",
        "schema_version": "0.1.0",
        "event_id": "evt-{}-repair-round-{}".format(task_id, compact_mtime),
        "event_type": "REPAIR_ROUND",
        "task_id": task_id,
        "created_at": created_at,
        "summary": "Task {} entered NEEDS_FIX; repair-round marker recorded.".format(task_id),
    }
    return append_event_once(events_path, event)


def iter_active_markdown(inbox):
    for root, dirs, files in os.walk(inbox):
        dirs[:] = [
            item for item in dirs
            if item not in {"archive", "artifacts", "__pycache__"}
        ]
        for filename in sorted(files):
            if filename.endswith(".md"):
                yield os.path.join(root, filename)


def git(workspace, *args):
    result = subprocess.run(
        ["git", "-C", workspace] + list(args),
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.rstrip(), result.stderr.rstrip()


def changed_paths(workspace):
    code, stdout, stderr = git(
        workspace, "status", "--porcelain=v1", "-z", "--untracked-files=all"
    )
    if code != 0:
        return None, stderr or "git status failed"
    paths = []
    records = stdout.split("\0")
    index = 0
    while index < len(records):
        record = records[index]
        if not record:
            index += 1
            continue
        if len(record) < 4:
            return None, "malformed git status record"
        status = record[:2]
        paths.append(record[3:].replace("\\", "/"))
        index += 1
        if "R" in status or "C" in status:
            if index >= len(records) or not records[index]:
                return None, "malformed git rename/copy record"
            if "R" in status:
                paths.append(records[index].replace("\\", "/"))
            index += 1
    return sorted(set(paths)), None


def split_allowed(value):
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value or "").replace(";", ",").split(",")
    return [
        item.strip().replace("\\", "/").rstrip("/")
        for item in raw
        if str(item).strip()
    ]


def _strip_dot_slash(value):
    """Strip a single leading './' prefix, not a character set.

    str.lstrip('./') treats the argument as the set {'.', '/'} and would also
    eat a lone leading '.' or '/' (e.g. '.secret' -> 'secret'), silently
    over-matching dotfiles. Only the './' relative-path prefix is intended.
    """
    normalized = value.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def path_allowed(path, allowed):
    normalized = _strip_dot_slash(path)
    for area in allowed:
        candidate = _strip_dot_slash(area)
        if normalized == candidate or normalized.startswith(candidate + "/"):
            return True
    return False


def path_is_within(path, parent):
    try:
        return os.path.commonpath(
            [os.path.normcase(path), os.path.normcase(parent)]
        ) == os.path.normcase(parent)
    except ValueError:
        return False


def resolve_declared_report_path(inbox, report_path):
    value = str(report_path or "").strip()
    if not value:
        return ""
    normalized = value.replace("\\", "/")
    if (
        os.path.basename(inbox).lower() == ".agent-inbox"
        and normalized.startswith(".agent-inbox/")
    ):
        candidate = os.path.abspath(os.path.join(os.path.dirname(inbox), value))
    elif os.path.isabs(value):
        candidate = os.path.abspath(value)
    else:
        candidate = os.path.abspath(os.path.join(inbox, value))
    inbox_abs = os.path.abspath(inbox)
    if not path_is_within(candidate, inbox_abs):
        return ""
    return candidate


def report_claims_source_changes(report):
    if not report:
        return False
    changed = report.get("data", {}).get("changed_files")
    if isinstance(changed, list):
        items = changed
    else:
        items = str(changed or "").replace(";", ",").split(",")
    meaningful = [
        str(item).strip().lower()
        for item in items
        if str(item).strip()
    ]
    return any(item not in {"none", "n/a", "unknown"} for item in meaningful)


def exclude_coordination_paths(paths, workspace, inbox):
    try:
        relative_inbox = os.path.relpath(inbox, workspace)
    except ValueError:
        return paths
    normalized = relative_inbox.replace("\\", "/").strip("/")
    if normalized == ".." or normalized.startswith("../"):
        return paths
    return [
        path for path in paths
        if path != normalized and not path.startswith(normalized + "/")
    ]


def run_validator(tasks, reports):
    paths = []
    for task_id in sorted(tasks):
        paths.append(tasks[task_id]["path"])
        report = reports.get(task_id)
        if report:
            paths.append(report["path"])
    target_dir = os.path.dirname(paths[0]) if paths else ""
    result = validate_paths(
        paths,
        cross_check=True,
        target_dir=target_dir,
    )
    return result["ok"], format_validation_result(result)[:20]


def run_file_validator(path):
    """Validate one task or report file without cross-file attribution bleed."""
    result = validate_paths([path])
    return result["ok"], format_validation_result(result)[:12]


def compact_json_result(result, verbose=False):
    """Hide successful validator transcripts unless explicitly requested."""
    if verbose:
        return result
    compact = copy.deepcopy(result)
    if compact.get("validator_ok"):
        compact.pop("validator_output", None)
    if compact.get("batch_validator_ok"):
        compact.pop("batch_validator_output", None)
    for task in compact.get("tasks", []):
        if task.get("task_contract_ok"):
            task.pop("task_contract_output", None)
        if task.get("report_schema_ok"):
            task.pop("report_schema_output", None)
        if task.get("task_report_consistency_ok"):
            task.pop("task_report_consistency_output", None)
    return compact


def compact_repair_hints(issues):
    """Return deterministic short repair hints for common contract failures."""
    return [
        REPAIR_HINTS[issue]
        for issue in sorted(set(issues))
        if issue in REPAIR_HINTS
    ]


def scan(inbox, selected_task_ids, run_validation=True):
    tasks = {}
    reports = {}
    parse_errors = []
    for path in iter_active_markdown(inbox):
        data, errors = parse_frontmatter(path)
        if errors:
            basename = os.path.basename(path).lower()
            if not selected_task_ids and basename.startswith(("task-", "report-")):
                parse_errors.extend(errors)
            continue
        if data is None:
            continue
        schema = data.get("schema")
        task_id = str(data.get("task_id") or "").strip()
        if not task_id:
            continue
        item = {"path": path, "data": data}
        if schema == "agent-file-coordination/task":
            if task_id in tasks:
                if not selected_task_ids or task_id in selected_task_ids:
                    parse_errors.append("duplicate task_id {}".format(task_id))
            tasks[task_id] = item
        elif schema == "agent-file-coordination/report":
            if task_id in reports:
                if not selected_task_ids or task_id in selected_task_ids:
                    parse_errors.append("duplicate report {}".format(task_id))
            reports[task_id] = item

    missing_task_ids = sorted(selected_task_ids - set(tasks))
    active_tasks = {}
    for task_id, task in tasks.items():
        if selected_task_ids and task_id not in selected_task_ids:
            continue
        status = str(task["data"].get("status") or "").upper()
        if status not in CLOSED_STATUSES:
            active_tasks[task_id] = task
    batch_validator_ok, batch_validator_lines = run_validator(active_tasks, reports)
    results = []
    for task_id in sorted(active_tasks):
        task = active_tasks[task_id]
        data = task["data"]
        report = reports.get(task_id)
        task_contract_ok, task_contract_lines = run_file_validator(task["path"])
        declared_report_path = resolve_declared_report_path(
            inbox, data.get("report_path", "")
        )
        declared_report_invalid = False
        if report is None and declared_report_path and os.path.isfile(
            declared_report_path
        ):
            report = {"path": declared_report_path, "data": {}}
            declared_report_invalid = True
        if report:
            report_schema_ok, report_schema_lines = run_file_validator(
                report["path"]
            )
            if declared_report_invalid:
                pair_contract_ok = False
                pair_contract_lines = [
                    "declared report_path exists but is not a schema-valid AFC report"
                ]
            else:
                pair_contract_ok, pair_contract_lines = run_validator(
                    {task_id: task}, {task_id: report}
                )
        else:
            report_schema_ok = False
            report_schema_lines = ["report missing"]
            pair_contract_ok = False
            pair_contract_lines = ["report missing"]
        workspace = data.get("workspace")
        workspace = workspace if isinstance(workspace, dict) else {}
        workspace_path = str(workspace.get("path") or "")
        branch_expected = str(workspace.get("branch") or "")
        base_expected = str(workspace.get("base") or "")
        allowed = split_allowed(workspace.get("locked_files_or_areas"))
        permission_scope = data.get("permission_scope")
        permission_scope = (
            permission_scope if isinstance(permission_scope, dict) else {}
        )
        modify_source = str(permission_scope.get("modify_source") or "").lower()
        workspace_mode = str(workspace.get("mode") or "")
        role = str(data.get("role") or "")
        budget = (
            REVIEW_REPORT_BUDGET_BYTES
            if role == "reviewer"
            else REPORT_BUDGET_BYTES
        )
        issues = []
        warnings = []
        report_size = 0
        contract_issues = []
        if not task_contract_ok:
            contract_issues.append("TASK_CONTRACT_INVALID")
        if declared_report_invalid:
            contract_issues.append("REPORT_SCHEMA_INVALID_AT_DECLARED_PATH")
        elif report and not report_schema_ok:
            contract_issues.append("REPORT_SCHEMA_INVALID")
        if report and not declared_report_invalid and not pair_contract_ok:
            contract_issues.append("TASK_REPORT_CONSISTENCY_FAILED")
        issues.extend(contract_issues)
        if not report:
            issues.append("REPORT_MISSING")
        else:
            report_size = os.path.getsize(report["path"])
            if report_size > budget:
                issues.append("REPORT_OVER_BUDGET")

        branch_actual = ""
        head_actual = ""
        paths = []
        if not workspace_path or not os.path.isdir(workspace_path):
            issues.append("WORKSPACE_MISSING")
        else:
            code, branch_actual, _ = git(workspace_path, "branch", "--show-current")
            if code != 0:
                issues.append("NOT_A_GIT_WORKSPACE")
            else:
                _, head_actual, _ = git(workspace_path, "rev-parse", "HEAD")
                paths, status_error = changed_paths(workspace_path)
                if status_error:
                    issues.append("GIT_STATUS_FAILED")
                    paths = []
                else:
                    paths = exclude_coordination_paths(
                        paths, workspace_path, inbox
                    )
                if branch_expected and branch_actual != branch_expected:
                    issues.append("BRANCH_MISMATCH")
                if base_expected:
                    code, base_resolved, _ = git(
                        workspace_path, "rev-parse", base_expected
                    )
                    if code != 0 or head_actual != base_resolved:
                        issues.append("BASE_MISMATCH")
                if not allowed:
                    warnings.append("NO_LOCKED_SCOPE")
                else:
                    outside = [path for path in paths if not path_allowed(path, allowed)]
                    if outside:
                        read_only_reviewer = (
                            role == "reviewer"
                            and workspace_mode == "read_only_shared"
                            and modify_source not in {"yes", "true"}
                            and not report_claims_source_changes(report)
                        )
                        if read_only_reviewer:
                            warnings.append(
                                "pre_existing_dirty_paths=" + ",".join(outside)
                            )
                        else:
                            issues.append("OUT_OF_SCOPE_CHANGES")
                            warnings.append("outside_scope=" + ",".join(outside))

        lock_scope_ok = "OUT_OF_SCOPE_CHANGES" not in issues

        # Coordinator-side code re-verification (graded, deterministic). Only the
        # rare high-risk tasks (release ops or heaviest tiers) re-run the task's
        # validation_command first-hand; everything else trusts the worker's
        # self-run evidence. The agent only reads PASS/FAIL, so token cost stays
        # near zero and the duplicated compute is spent only where it matters.
        validation_command = str(data.get("validation_command") or "").strip()
        if (
            run_validation
            and report
            and not declared_report_invalid
            and validation_command
            and should_reverify(data)
            and workspace_path
            and os.path.isdir(workspace_path)
            and "NOT_A_GIT_WORKSPACE" not in issues
        ):
            rc, tail = run_validation_command(validation_command, workspace_path)
            if rc != 0:
                issues.append("VALIDATION_COMMAND_FAILED")
                warnings.append("validation_command_exit={}".format(rc))
                if tail:
                    warnings.append(
                        "validation_command_tail=" + tail.replace("\n", " | ")
                    )

        results.append({
            "task_id": task_id,
            "agent_name": data.get("agent_name", ""),
            "ready_for_review": not issues,
            "issues": sorted(set(issues)),
            "blocking_reasons": sorted(set(issues)),
            "blocked_by_task_ids": [task_id] if issues else [],
            "task_contract_ok": task_contract_ok,
            "task_contract_output": task_contract_lines,
            "report_schema_ok": report_schema_ok,
            "report_schema_output": report_schema_lines,
            "task_report_consistency_ok": pair_contract_ok,
            "task_report_consistency_output": pair_contract_lines,
            "lock_scope_ok": lock_scope_ok,
            "repair_hints": compact_repair_hints(issues),
            "warnings": warnings,
            "repair_round_count": 0,
            "report_path": report["path"] if report else "",
            "report_size_bytes": report_size,
            "report_budget_bytes": budget,
            "workspace": workspace_path,
            "expected_branch": branch_expected,
            "actual_branch": branch_actual,
            "expected_base": base_expected,
            "actual_head": head_actual,
            "changed_paths": paths,
            "allowed_areas": allowed,
        })

    # --- Repair-round budget tracking ---
    events_path = os.path.join(inbox, "events.jsonl")
    today = str(
        __import__("datetime").datetime.now(__import__("datetime").timezone.utc).date()
    )
    for item in results:
        if not item["ready_for_review"]:
            task_id = item["task_id"]
            round_count = count_repair_rounds(events_path, task_id)
            # Only a real report revision consumes a repair-round slot. If the
            # report is missing (e.g. a REPORT_MISSING diagnosis run before any
            # worker submission), do not append a marker: appending with an
            # empty mtime would burn one MAX_EXPECTED_ROUNDS slot and make the
            # next real NEEDS_FIX reach the escalation budget one round early.
            report_mtime = ""
            rp = item.get("report_path", "")
            if rp and os.path.isfile(rp):
                report_mtime = str(os.path.getmtime(rp))
            if report_mtime:
                appended = append_repair_round_event(
                    events_path, task_id, today, report_mtime
                )
                if appended:
                    round_count += 1
            item["repair_round_count"] = round_count
            if round_count >= MAX_EXPECTED_ROUNDS:
                item["warnings"].append(
                    "REPAIR_ROUND_BUDGET_REACHED: {} repair rounds reached "
                    "MAX_EXPECTED_ROUNDS ({}); escalation or independent "
                    "review required.".format(round_count, MAX_EXPECTED_ROUNDS)
                )

    return {
        "inbox": inbox,
        "validator_ok": batch_validator_ok,
        "validator_output": batch_validator_lines,
        "batch_validator_ok": batch_validator_ok,
        "batch_validator_output": batch_validator_lines,
        "parse_errors": parse_errors,
        "missing_task_ids": missing_task_ids,
        "tasks": results,
        "ready_count": sum(1 for item in results if item["ready_for_review"]),
        "needs_fix_count": sum(1 for item in results if not item["ready_for_review"]),
        "blocked_by_task_ids": sorted(
            item["task_id"] for item in results if not item["ready_for_review"]
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Validate all arrived reports and worker worktrees in one pass."
    )
    parser.add_argument("inbox")
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="include successful validator transcripts in JSON output",
    )
    parser.add_argument(
        "--skip-validation-command",
        action="store_true",
        help="do not re-run validation_command for high-risk tasks",
    )
    args = parser.parse_args()

    inbox = os.path.abspath(args.inbox)
    if not os.path.isdir(inbox):
        print("error: inbox not found: {}".format(inbox), file=sys.stderr)
        return 1
    result = scan(
        inbox,
        set(args.task_id),
        run_validation=not args.skip_validation_command,
    )
    if args.json:
        print(json.dumps(
            compact_json_result(result, verbose=args.verbose),
            indent=2,
            ensure_ascii=False,
        ))
    else:
        print(
            "ready={} needs_fix={} validator={}".format(
                result["ready_count"],
                result["needs_fix_count"],
                "pass" if result["validator_ok"] else "fail",
            )
        )
        for task in result["tasks"]:
            state = "READY" if task["ready_for_review"] else "NEEDS_FIX"
            details = ",".join(task["issues"]) or "none"
            print("{} {} issues={}".format(state, task["task_id"], details))
            for warning in task.get("warnings", []):
                if "REPAIR_ROUND_BUDGET_REACHED" in warning:
                    print("  WARNING: {}".format(warning))
        for error in result["parse_errors"]:
            print("ERROR {}".format(error))
        for task_id in result["missing_task_ids"]:
            print("ERROR task_id not found: {}".format(task_id))

    if result["parse_errors"] or result["missing_task_ids"]:
        return 1
    return 2 if result["needs_fix_count"] else 0


if __name__ == "__main__":
    sys.exit(main())
