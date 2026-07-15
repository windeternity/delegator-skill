#!/usr/bin/env python3
"""CAL-3 headless CLI worker dispatcher.

The dispatcher starts local non-interactive CLI workers, captures their logs,
and validates the exact expected report after the worker process exits. Worker
stdout is never trusted as completion evidence. The CAL-2 watcher is only used
as a best-effort intake/dashboard compatibility path after direct validation.

Usage:
    python -B scripts/afc-cal3-dispatch.py --inbox .agent-inbox --task-id <ID>
"""

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import date, datetime, timezone

try:
    from afc_event import add_event_context, append_event_once
    from afc_frontmatter import (
        parse_frontmatter_flat,
        extract_structured_frontmatter,
    )
    from afc_roster import format_roster_block, maybe_warn_roster, require_usable_roster, resolve_recipes, resolve_roster
    from afc_validation import validate_report_schema
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from afc_event import add_event_context, append_event_once
    from afc_frontmatter import (
        parse_frontmatter_flat,
        extract_structured_frontmatter,
    )
    from afc_roster import format_roster_block, maybe_warn_roster, require_usable_roster, resolve_recipes, resolve_roster
    from afc_validation import validate_report_schema


PROFILES = {
    "cal3-readonly": {
        "modify_source": False,
        "run_commands": "read_only",
        "network_access": "none",
        "commit_push": "no",
    },
    "cal3-bounded-edit": {
        "modify_source": True,
        "run_commands": "tests_only",
        "network_access": "none",
        "commit_push": "no",
    },
    "cal3-local-autonomous": {
        "modify_source": True,
        "run_commands": "bounded",
        "network_access": "docs_only",
        "commit_push": "no",
    },
    "cal3-local-autonomous-high": {
        "modify_source": True,
        "run_commands": "bounded",
        "network_access": "none",
        "commit_push": "no",
    },
    "cal3-network-readonly": {
        "modify_source": False,
        "run_commands": "read_only",
        "network_access": "allowed",
        "commit_push": "no",
    },
    "cal3-network-work": {
        "modify_source": True,
        "run_commands": "bounded",
        "network_access": "allowed",
        "commit_push": "no",
    },
    "cal3-approved-commit": {
        "modify_source": True,
        "run_commands": "bounded",
        "network_access": "allowed",
        "commit_push": "approved",
    },
    "cal3-release-gated": {
        "modify_source": True,
        "run_commands": "bounded",
        "network_access": "allowed",
        "commit_push": "approved",
    },
}

RUN_RANK = {"none": 0, "read_only": 1, "tests_only": 2, "bounded": 3}
NET_RANK = {"none": 0, "docs_only": 1, "allowed": 2}
COMMIT_RANK = {"no": 0, "ask": 1, "approved": 2}
SKIP_DIRS = {"archive", "artifacts", "__pycache__"}
SECRET_PATTERNS = [
    (
        re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s]+)"),
        lambda m: "{}=<redacted>".format(m.group(1)),
    ),
    (
        re.compile(r"(?i)(bearer)\s+[A-Za-z0-9._~+/=-]+"),
        lambda m: "{} <redacted>".format(m.group(1)),
    ),
    (
        re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{20,}"),
        lambda m: "<redacted-secret>",
    ),
]
DEFAULT_ABORT_FAILURE_PATTERN = r"(?i)(?:status(?:\s+code)?|http|->)[^\n\r]*\b[45]\d\d\b"


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def status_line(state, task_id=None, **fields):
    parts = ["CAL3_STATUS", "state={}".format(state)]
    if task_id:
        parts.append("task_id={}".format(task_id))
    for key in sorted(fields):
        value = fields[key]
        if value is not None:
            parts.append("{}={}".format(key, value))
    print(" ".join(parts), flush=True)


def emit_json(state, task_id=None, **fields):
    payload = {"state": state}
    if task_id:
        payload["task_id"] = task_id
    payload.update({k: v for k, v in fields.items() if v is not None})
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def emit(args, state, task_id=None, **fields):
    if args.json:
        emit_json(state, task_id, **fields)
    else:
        status_line(state, task_id, **fields)


def redact_text(text):
    redacted = text
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def tail_redacted(path, lines=80):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            content = handle.readlines()
    except OSError:
        return ""
    return redact_text("".join(content[-lines:]))


def file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def read_from_offset(path, offset):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            text = handle.read()
            return text, handle.tell()
    except OSError:
        return "", offset


def last_nonempty_line(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError:
        return ""
    for line in reversed(lines):
        stripped = line.strip()
        if stripped:
            return redact_text(stripped)
    return ""


def primary_log_path(stdout_path, stderr_path):
    if file_size(stderr_path) > 0:
        return stderr_path
    return stdout_path


def combined_log_tail(stdout_path, stderr_path, lines=80):
    parts = []
    stdout_tail = tail_redacted(stdout_path, lines)
    stderr_tail = tail_redacted(stderr_path, lines)
    if stdout_tail:
        parts.append("stdout:\n{}".format(stdout_tail))
    if stderr_tail:
        parts.append("stderr:\n{}".format(stderr_tail))
    return "\n".join(parts)


def write_log_readme(log_dir):
    text = """# CAL-3 Worker Logs

- `stderr.log` often contains the live worker trace for `codex exec`; it may be the primary log.
- `stdout.log` may be empty and is not completion evidence.
- Completion still requires the exact schema-valid report file declared by the task.
- `status.json` records redacted log tails, primary log selection, timeout/abort details, and report validation.
"""
    with open(os.path.join(log_dir, "LOGS.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def subprocess_startup_kwargs():
    if os.name == "nt":
        return {}
    return {"start_new_session": True}


def fallback_terminate_process(process):
    result = {"method": "terminate", "pid": process.pid}
    try:
        process.terminate()
        try:
            result["exit_code"] = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            result["method"] = "kill"
            result["exit_code"] = process.wait(timeout=5)
    except OSError as exc:
        result["error"] = str(exc)
    return result


def terminate_process_tree(process):
    result = {"attempted": True, "pid": process.pid}
    if process.poll() is not None:
        result["method"] = "already_exited"
        result["exit_code"] = process.returncode
        return result

    if os.name == "nt":
        result["method"] = "taskkill"
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                shell=False,
            )
            result["return_code"] = completed.returncode
            if completed.stderr:
                result["stderr"] = completed.stderr.strip()[:500]
            if completed.stdout:
                result["stdout"] = completed.stdout.strip()[:500]
            try:
                result["exit_code"] = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                result["fallback"] = fallback_terminate_process(process)
        except (OSError, subprocess.TimeoutExpired) as exc:
            result["error"] = str(exc)
            result["fallback"] = fallback_terminate_process(process)
        return result

    result["method"] = "process_group"
    try:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            result["exit_code"] = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            result["signal"] = "SIGKILL"
            result["exit_code"] = process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["error"] = str(exc)
        result["fallback"] = fallback_terminate_process(process)
    return result


def termination_exit_code(termination):
    if not isinstance(termination, dict):
        return None
    if "exit_code" in termination:
        return termination.get("exit_code")
    fallback = termination.get("fallback")
    if isinstance(fallback, dict):
        return fallback.get("exit_code")
    return None


def relpath_posix(path, root):
    return os.path.relpath(path, root).replace("\\", "/")


def parse_task(filepath):
    data, err = parse_frontmatter_flat(filepath, strict=False)
    if err or not data:
        return None, err or "missing task frontmatter"
    if data.get("schema") != "agent-file-coordination/task":
        return None, "not a task file: {}".format(filepath)
    data["_filepath"] = filepath
    return data, None


def iter_markdown_files(inbox_dir):
    for root, dirs, files in os.walk(inbox_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for filename in sorted(files):
            if filename.endswith(".md"):
                yield os.path.join(root, filename)


def find_task(inbox_dir, task_id):
    matches = []
    for filepath in iter_markdown_files(inbox_dir):
        data, err = parse_task(filepath)
        if err or not data:
            continue
        if data.get("task_id", "").strip() == task_id:
            matches.append(data)
    if not matches:
        return None, "no task found for task_id '{}'".format(task_id)
    if len(matches) > 1:
        return None, "duplicate tasks found for task_id '{}'".format(task_id)
    return matches[0], None


def bool_enabled(value):
    return str(value or "").strip().lower() in {"yes", "true", "approved"}


def normalized(value):
    return str(value or "").strip().lower()


def require_rank(value, rank_map, max_value, field_name):
    value = normalized(value)
    if value not in rank_map:
        return "invalid {}: {}".format(field_name, value)
    if rank_map[value] > rank_map[max_value]:
        return "{} {} exceeds CAL-3 profile limit {}".format(
            field_name, value, max_value
        )
    return None


def check_permission(task, profile_name):
    if profile_name not in PROFILES:
        return "unknown permission profile: {}".format(profile_name)
    profile = PROFILES[profile_name]

    if bool_enabled(task.get("permission_scope.destructive_actions")):
        return "destructive_actions must remain disabled for CAL-3"

    if bool_enabled(task.get("permission_scope.modify_source")):
        if not profile["modify_source"]:
            return "task requires modify_source but profile is read-only"

    err = require_rank(
        task.get("permission_scope.run_commands", "none"),
        RUN_RANK,
        profile["run_commands"],
        "run_commands",
    )
    if err:
        return err

    err = require_rank(
        task.get("permission_scope.network_access", "none"),
        NET_RANK,
        profile["network_access"],
        "network_access",
    )
    if err:
        return err

    commit_push = normalized(task.get("permission_scope.commit_push", "no"))
    if commit_push not in COMMIT_RANK:
        return "invalid commit_push: {}".format(commit_push)
    if COMMIT_RANK[commit_push] > COMMIT_RANK[profile["commit_push"]]:
        return "commit_push {} exceeds CAL-3 profile limit {}".format(
            commit_push, profile["commit_push"]
        )
    return None


def profile_allows_commit(profile_name):
    profile = PROFILES.get(profile_name, {})
    return normalized(profile.get("commit_push", "no")) == "approved"


def check_cli_capability(task, recipe):
    capability = recipe.get("capability") or {}
    if not isinstance(capability, dict):
        capability = {}
    modify_cap = bool_enabled(capability.get("modify_source", "yes"))
    run_cap = normalized(capability.get("run_commands", "bounded"))
    net_cap = normalized(capability.get("network_access", "allowed"))
    commit_cap = normalized(capability.get("commit_push", "approved"))

    if bool_enabled(task.get("permission_scope.modify_source")) and not modify_cap:
        return "task requires modify_source but CLI capability is read-only"
    err = require_rank(
        task.get("permission_scope.run_commands", "none"),
        RUN_RANK,
        run_cap if run_cap in RUN_RANK else "none",
        "run_commands",
    )
    if err:
        return "CLI capability: {}".format(err)
    err = require_rank(
        task.get("permission_scope.network_access", "none"),
        NET_RANK,
        net_cap if net_cap in NET_RANK else "none",
        "network_access",
    )
    if err:
        return "CLI capability: {}".format(err)
    err = require_rank(
        task.get("permission_scope.commit_push", "no"),
        COMMIT_RANK,
        commit_cap if commit_cap in COMMIT_RANK else "no",
        "commit_push",
    )
    if err:
        return "CLI capability: {}".format(err)
    return None


def path_is_within(path, parent):
    try:
        return os.path.commonpath(
            [os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(parent))]
        ) == os.path.normcase(os.path.abspath(parent))
    except ValueError:
        return False


def ignored_source_path(path, workspace, inbox_dir, report_path=None):
    rel = relpath_posix(path, workspace)
    parts = rel.split("/")
    if not rel or rel == ".":
        return True
    if path_is_within(path, inbox_dir):
        return True
    if report_path and os.path.abspath(path) == os.path.abspath(report_path):
        return True
    if parts[0].startswith("."):
        return True
    return any(part in SKIP_DIRS or part.startswith(".") for part in parts)


def porcelain_path(line):
    raw = line[3:].strip() if len(line) > 3 else line.strip()
    if " -> " in raw:
        raw = raw.split(" -> ", 1)[1].strip()
    return raw.strip('"')


def git_source_snapshot(workspace, inbox_dir, report_path):
    try:
        root_result = subprocess.run(
            ["git", "-C", workspace, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
        if root_result.returncode != 0:
            return None
        git_root = os.path.abspath((root_result.stdout or "").strip())
        if os.path.normcase(git_root) != os.path.normcase(os.path.abspath(workspace)):
            return None
        result = subprocess.run(
            ["git", "-C", workspace, "status", "--porcelain=v1", "--untracked-files=all"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    entries = {}
    for line in (result.stdout or "").splitlines():
        if not line.strip():
            continue
        rel = porcelain_path(line).replace("\\", "/")
        abs_path = os.path.abspath(os.path.join(workspace, rel))
        if ignored_source_path(abs_path, workspace, inbox_dir, report_path):
            continue
        digest = None
        if os.path.isfile(abs_path):
            try:
                digest = file_digest(abs_path)
            except OSError:
                digest = None
        entries[rel] = (line[:2], digest)
    return {"mode": "git", "entries": entries}


def file_digest(path):
    digest = hashlib.sha1()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def filesystem_source_snapshot(workspace, inbox_dir, report_path):
    entries = {}
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in SKIP_DIRS
        ]
        for filename in files:
            path = os.path.abspath(os.path.join(root, filename))
            if ignored_source_path(path, workspace, inbox_dir, report_path):
                continue
            try:
                stat = os.stat(path)
                entries[relpath_posix(path, workspace)] = (
                    stat.st_size,
                    stat.st_mtime_ns,
                    file_digest(path),
                )
            except OSError:
                entries[relpath_posix(path, workspace)] = None
    return {"mode": "filesystem", "entries": entries}


def source_snapshot(workspace, inbox_dir, report_path):
    # Snapshot is workspace-wide, not scoped to the task's locked files. With
    # --max-workers > 1, concurrent tasks must use separate worktrees: a shared
    # workspace.path lets one worker's edits surface in another's readonly diff.
    snapshot = git_source_snapshot(workspace, inbox_dir, report_path)
    if snapshot is not None:
        return snapshot
    return filesystem_source_snapshot(workspace, inbox_dir, report_path)


def source_changes(before, after):
    if not before or not after or before.get("mode") != after.get("mode"):
        return []
    before_entries = before.get("entries") or {}
    after_entries = after.get("entries") or {}
    if isinstance(before_entries, set) and isinstance(after_entries, set):
        changed = sorted(after_entries - before_entries)
        return [entry[3:] if len(entry) > 3 else entry for entry in changed]
    paths = set(before_entries) | set(after_entries)
    return sorted(
        path for path in paths
        if before_entries.get(path) != after_entries.get(path)
    )


def git_history_snapshot(workspace):
    try:
        root_result = subprocess.run(
            ["git", "-C", workspace, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
        if root_result.returncode != 0:
            return None
        git_root = os.path.abspath((root_result.stdout or "").strip())
        if os.path.normcase(git_root) != os.path.normcase(os.path.abspath(workspace)):
            return None
        head_result = subprocess.run(
            ["git", "-C", workspace, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
        branch_result = subprocess.run(
            ["git", "-C", workspace, "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if head_result.returncode != 0:
        return None
    branch = ""
    if branch_result.returncode == 0:
        branch = (branch_result.stdout or "").strip()
    return {
        "head": (head_result.stdout or "").strip(),
        "branch": branch,
    }


def git_history_changes(before, after):
    if not before or not after:
        return []
    changes = []
    if before.get("head") != after.get("head"):
        changes.append("HEAD moved from {} to {}".format(
            before.get("head", "")[:12],
            after.get("head", "")[:12],
        ))
    if before.get("branch") != after.get("branch"):
        changes.append("branch changed from {} to {}".format(
            before.get("branch") or "<detached>",
            after.get("branch") or "<detached>",
        ))
    return changes


def recipe_uses_workspace_sandbox(recipe, profile_name, argv):
    profile_args = recipe.get("profile_args", {}).get(profile_name, {})
    if not isinstance(profile_args, dict):
        profile_args = {}
    sandbox = str(profile_args.get("codex_sandbox", "")).strip()
    if sandbox in {"workspace-write", "read-only"}:
        return True
    return any(str(item) in {"workspace-write", "read-only"} for item in argv)


def _nested_task_for_validation(task):
    """Rebuild permission_scope as a nested dict for validate_report_schema.

    CAL-3 dispatch tasks come from parse_frontmatter_flat, which stores
    nested fields as dotted keys (e.g. permission_scope.modify_source).
    validate_report_schema's modify_source cross-check only fires when
    task['permission_scope'] is a dict, so rebuild that one group from the
    dotted keys; top-level fields (agent_name, coordination_mode,
    comparison_group) are already flat-correct and are left untouched.
    """
    if not task or isinstance(task.get("permission_scope"), dict):
        return task
    nested = dict(task)
    scope = {}
    for key, value in task.items():
        if isinstance(key, str) and key.startswith("permission_scope."):
            scope[key[len("permission_scope."):]] = value
    if scope:
        nested["permission_scope"] = scope
    return nested


def validate_expected_report(report_path, expected_task_id, task=None):
    # Structured parse preserves list-block fields (evidence_refs etc.) as
    # real lists; the flat/nested parser collapses them to "", which would
    # bypass validate_report_schema's non-empty-list check. Matches the
    # canonical validator (afc_inbox_validation) contract.
    data, body, errs = extract_structured_frontmatter(report_path)
    if errs:
        return False, "parse error: {}".format("; ".join(errs))
    if not data:
        return False, "empty frontmatter"
    if data.get("schema") != "agent-file-coordination/report":
        return False, "wrong schema: {}".format(data.get("schema"))
    report_task_id = str(data.get("task_id", "")).strip()
    if expected_task_id and report_task_id != expected_task_id:
        return False, "task_id mismatch: expected '{}', got '{}'".format(
            expected_task_id, report_task_id
        )
    # Pass the parsed task so the agent_name / coordination_mode /
    # comparison_group / modify_source cross-checks inside
    # validate_report_schema run here at dispatch intake, not later at the
    # intake stage. Mirrors afc-watch.py's two call sites. The CAL-3 dispatch
    # task is flat-parsed, so nest its permission_scope.* dotted keys
    # (_nested_task_for_validation) or the modify_source check would be
    # silently skipped.
    is_valid, reasons = validate_report_schema(
        data, body=body, task=_nested_task_for_validation(task)
    )
    if not is_valid:
        return False, "; ".join(reasons)
    return True, None


def source_readonly_required(task, profile_name):
    return (
        not PROFILES[profile_name]["modify_source"]
        or not bool_enabled(task.get("permission_scope.modify_source"))
    )


def resolve_task_path(task):
    return os.path.abspath(task["_filepath"])


def resolve_workspace(task):
    workspace = task.get("workspace.path", "").strip()
    if not workspace:
        return None
    return os.path.abspath(workspace)


def resolve_report_path(task, inbox_dir):
    report_path = task.get("report_path", "").strip()
    if not report_path:
        return None
    normalized = report_path.replace("\\", "/")
    if normalized.startswith(".agent-inbox/"):
        return os.path.abspath(
            os.path.join(inbox_dir, normalized[len(".agent-inbox/"):])
        )
    if os.path.isabs(report_path):
        return os.path.abspath(report_path)
    return os.path.abspath(os.path.join(inbox_dir, report_path))


def read_recipes(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except OSError as exc:
        return None, "could not read recipe file: {}".format(exc)
    except json.JSONDecodeError as exc:
        return None, "invalid recipe JSON: {}".format(exc)
    if not isinstance(data, dict):
        return None, "recipe file must contain a JSON object"
    return data, None


def count_started_events(events_path, task_id):
    count = 0
    if not os.path.isfile(events_path):
        return count
    try:
        with open(events_path, "r", encoding="utf-8-sig") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if (
                    event.get("event_type") == "TASK_STARTED"
                    and event.get("task_id") == task_id
                ):
                    count += 1
    except OSError:
        return count
    return count


def choose_recipe(task, recipes_data):
    agent_name = task.get("agent_name", "").strip()
    agent_map = recipes_data.get("agent_recipes", {})
    recipes = recipes_data.get("recipes", {})
    if not isinstance(agent_map, dict) or not isinstance(recipes, dict):
        return None, "recipe file must contain agent_recipes and recipes objects"
    recipe_id = agent_map.get(agent_name) or agent_map.get(agent_name.lower()) or agent_name
    if recipe_id not in recipes and recipe_id.lower() in recipes:
        recipe_id = recipe_id.lower()
    if recipe_id not in recipes:
        return None, "no CAL-3 recipe for agent '{}'".format(agent_name)
    recipe = recipes[recipe_id]
    if not isinstance(recipe, dict):
        return None, "recipe '{}' must be an object".format(recipe_id)
    if "argv" not in recipe or not isinstance(recipe["argv"], list):
        return None, "recipe '{}' missing argv list".format(recipe_id)
    return (recipe_id, recipe), None


def prompt_for_task(task, workspace, task_path, report_path):
    # Include coordination metadata in the report template when the task
    # carries it, so a worker hand-writing a report (not using afc-report.py,
    # which already echoes these) writes coordination_mode / comparison_group
    # too. Otherwise the dispatch-time task cross-check would flag a mismatch
    # on coordinated CAL-3 tasks.
    coord_lines = ""
    _cm = str(task.get("coordination_mode") or "").strip()
    _cg = str(task.get("comparison_group") or "").strip()
    if _cm:
        coord_lines += "coordination_mode: {}\n".format(_cm)
    if _cg:
        coord_lines += "comparison_group: {}\n".format(_cg)
    return (
        "You are {agent}. Open this existing worktree as the project: {workspace}. "
        "Read this task file: {task_path}. Execute only that task within its "
        "Permission Scope and write a schema-valid report to: {report_path}. "
        "Do not commit, push, deploy, merge, delete files, read secrets, or "
        "expand permission scope unless the task explicitly authorizes it. "
        "If approval or interactive input is required, stop and report the blocker. "
        "Your report frontmatter must include nested YAML mappings for "
        "evidence_trust, guardrails, and validation, not strings or lists. "
        "Use this minimum report frontmatter shape and replace only the evidence "
        "or changed_files values as needed:\n"
        "---\n"
        "schema: agent-file-coordination/report\n"
        "schema_version: 0.1.0\n"
        "task_id: {task_id}\n"
        "agent_name: {agent}\n"
        "{coord_lines}"
        "verdict: GO\n"
        "changed_files:\n"
        "  - none\n"
        "evidence_refs:\n"
        "  - task-file\n"
        "evidence_trust:\n"
        "  trust_level: referenced\n"
        "  untrusted_inputs_seen: no\n"
        "  prompt_injection_suspected: no\n"
        "  permission_escalation_requested: no\n"
        "guardrails:\n"
        "  role_boundary_followed: yes\n"
        "  coordinator_verdict_given: no\n"
        "  permission_scope_expanded: no\n"
        "  secrets_private_data_printed: no\n"
        "  production_default_behavior_changed: no\n"
        "  commit_push_done: no\n"
        "  destructive_command_done: no\n"
        "validation:\n"
        "  tier: no-test-needed\n"
        "  result: pass\n"
        "reported_at: YYYY-MM-DD\n"
        "---"
    ).format(
        agent=task.get("agent_name", ""),
        task_id=task.get("task_id", ""),
        workspace=workspace,
        task_path=task_path,
        report_path=report_path,
        coord_lines=coord_lines,
    )


def fill_template(value, mapping):
    if not isinstance(value, str):
        return value
    result = value
    for key, replacement in mapping.items():
        result = result.replace("{" + key + "}", str(replacement))
    return result


def build_argv(recipe, profile_name, task, workspace, task_path, report_path):
    profile_args = recipe.get("profile_args", {}).get(profile_name, {})
    if not isinstance(profile_args, dict):
        profile_args = {}
    mapping = {
        "workspace": workspace,
        "task_path": task_path,
        "report_path": report_path,
        "prompt": prompt_for_task(task, workspace, task_path, report_path),
        "profile": profile_name,
        "codex_sandbox": profile_args.get("codex_sandbox", "workspace-write"),
    }
    for key, value in profile_args.items():
        mapping[key] = value

    argv = [fill_template(item, mapping) for item in recipe["argv"]]
    cwd = fill_template(recipe.get("cwd", workspace), mapping)
    env_overrides = {}
    recipe_env = recipe.get("env", {})
    if isinstance(recipe_env, dict):
        for key, value in recipe_env.items():
            env_overrides[str(key)] = fill_template(value, mapping)
    return argv, cwd, env_overrides


def merged_env(env_overrides):
    if not env_overrides:
        return None
    env = dict(os.environ)
    env.update(env_overrides)
    return env


def derive_watch_iterations(args, launch_specs):
    if args.watch_max_iterations is not None:
        return args.watch_max_iterations
    return 1


def event_base(event_id, event_type, task, created_at, summary):
    event = {
        "schema": "agent-file-coordination/event",
        "schema_version": "0.1.0",
        "event_id": event_id,
        "event_type": event_type,
        "task_id": task.get("task_id", ""),
        "agent_name": task.get("agent_name", ""),
        "created_at": created_at,
        "summary": summary,
    }
    return add_event_context(event, task, "dispatch" if event_type == "TASK_DISPATCHED" else "execution")


def append_dispatched(events_path, task, created_at, profile_name, recipe_id, log_dir):
    task_id = task.get("task_id", "")
    event = event_base(
        "evt-{}-dispatched".format(task_id),
        "TASK_DISPATCHED",
        task,
        created_at,
        "CAL-3 dispatched task {} to {}.".format(task_id, task.get("agent_name", "")),
    )
    event["cal3_permission_profile"] = profile_name
    event["invoke_recipe"] = recipe_id
    event["log_path"] = log_dir.replace("\\", "/")
    append_event_once(events_path, event)


def append_started(events_path, task, created_at, profile_name, recipe_id, log_dir, pid, attempt):
    task_id = task.get("task_id", "")
    event = event_base(
        "evt-{}-started-{}".format(task_id, pid),
        "TASK_STARTED",
        task,
        created_at,
        "CAL-3 started worker process for task {}.".format(task_id),
    )
    event["cal3_permission_profile"] = profile_name
    event["invoke_recipe"] = recipe_id
    event["worker_session_id"] = "pid:{}".format(pid)
    event["attempt"] = attempt
    event["log_path"] = log_dir.replace("\\", "/")
    append_event_once(events_path, event)


def append_worker_heartbeat(events_path, task, created_at, log_dir, pid, attempt, sequence, stdout_path, stderr_path, last_sizes):
    task_id = task.get("task_id", "")
    stdout_size = file_size(stdout_path)
    stderr_size = file_size(stderr_path)
    event = event_base(
        "evt-{}-heartbeat-{}-{}".format(task_id, pid, sequence),
        "WORKER_HEARTBEAT",
        task,
        created_at,
        "CAL-3 worker heartbeat for task {}.".format(task_id),
    )
    event["worker_session_id"] = "pid:{}".format(pid)
    event["attempt"] = attempt
    event["log_path"] = log_dir.replace("\\", "/")
    event["stdout_bytes"] = stdout_size
    event["stderr_bytes"] = stderr_size
    event["stdout_delta"] = max(0, stdout_size - last_sizes.get("stdout", 0))
    event["stderr_delta"] = max(0, stderr_size - last_sizes.get("stderr", 0))
    event["last_stderr_line"] = last_nonempty_line(stderr_path)
    append_event_once(events_path, event)
    return {"stdout": stdout_size, "stderr": stderr_size}


def append_task_aborted(events_path, task, created_at, reason, evidence_tail, termination, pid, attempt):
    task_id = task.get("task_id", "")
    event = event_base(
        "evt-{}-aborted-{}-{}".format(task_id, pid, attempt),
        "TASK_ABORTED",
        task,
        created_at,
        "CAL-3 aborted task {}: {}.".format(task_id, reason),
    )
    event["abort_reason"] = reason
    event["abort_evidence_tail"] = evidence_tail
    event["termination"] = termination
    event["worker_session_id"] = "pid:{}".format(pid)
    event["attempt"] = attempt
    append_event_once(events_path, event)


def monitor_processes(processes, args, events_path):
    active = {}
    now = time.time()
    for task_id, (process, stdout_handle, stderr_handle, spec) in processes.items():
        active[task_id] = {
            "process": process,
            "stdout_handle": stdout_handle,
            "stderr_handle": stderr_handle,
            "spec": spec,
            "deadline": now + max(1, args.timeout_seconds or int(spec["recipe"].get("timeout_seconds", 1800))),
            "last_progress_at": now,
            "last_sizes": {
                "stdout": file_size(spec["stdout_path"]),
                "stderr": file_size(spec["stderr_path"]),
            },
            "last_heartbeat_at": now,
            "heartbeat_sequence": 0,
            "stdout_offset": 0,
            "stderr_offset": 0,
            "failure_count": 0,
        }
    outcomes = {}
    failure_pattern = re.compile(args.abort_failure_pattern) if args.abort_on_repeated_failures > 0 else None

    def finish_exited_task(task_id, state, grace_seconds=0):
        process = state["process"]
        return_code = process.poll()
        if return_code is None and grace_seconds > 0:
            try:
                return_code = process.wait(timeout=grace_seconds)
            except subprocess.TimeoutExpired:
                return_code = None
        if return_code is None:
            return False
        outcomes[task_id] = {"return_code": return_code}
        state["stdout_handle"].close()
        state["stderr_handle"].close()
        del active[task_id]
        return True

    while active:
        now = time.time()
        for task_id in list(active):
            state = active[task_id]
            process = state["process"]
            spec = state["spec"]
            if finish_exited_task(task_id, state):
                continue

            stdout_size = file_size(spec["stdout_path"])
            stderr_size = file_size(spec["stderr_path"])
            if stdout_size > state["last_sizes"]["stdout"] or stderr_size > state["last_sizes"]["stderr"]:
                state["last_progress_at"] = now

            if failure_pattern:
                stdout_text, state["stdout_offset"] = read_from_offset(
                    spec["stdout_path"], state["stdout_offset"]
                )
                stderr_text, state["stderr_offset"] = read_from_offset(
                    spec["stderr_path"], state["stderr_offset"]
                )
                text = stdout_text + "\n" + stderr_text
                matches = failure_pattern.findall(text)
                state["failure_count"] += len(matches)
                if state["failure_count"] >= args.abort_on_repeated_failures:
                    if finish_exited_task(task_id, state, grace_seconds=0.2):
                        continue
                    termination = terminate_process_tree(process)
                    evidence_tail = combined_log_tail(
                        spec["stdout_path"],
                        spec["stderr_path"],
                        args.log_tail_lines,
                    )
                    append_task_aborted(
                        events_path,
                        spec["task"],
                        args.created_at,
                        "repeated_failures",
                        evidence_tail,
                        termination,
                        process.pid,
                        spec["attempt"],
                    )
                    outcomes[task_id] = {
                        "return_code": termination_exit_code(termination),
                        "state": "ABORTED",
                        "abort_reason": "repeated_failures",
                        "abort_evidence_tail": evidence_tail,
                        "abort_termination": termination,
                    }
                    state["stdout_handle"].close()
                    state["stderr_handle"].close()
                    del active[task_id]
                    continue

            if args.abort_on_no_progress_seconds > 0 and now - state["last_progress_at"] >= args.abort_on_no_progress_seconds:
                if finish_exited_task(task_id, state, grace_seconds=0.2):
                    continue
                termination = terminate_process_tree(process)
                evidence_tail = tail_redacted(primary_log_path(spec["stdout_path"], spec["stderr_path"]), args.log_tail_lines)
                append_task_aborted(
                    events_path,
                    spec["task"],
                    args.created_at,
                    "no_progress",
                    evidence_tail,
                    termination,
                    process.pid,
                    spec["attempt"],
                )
                outcomes[task_id] = {
                    "return_code": termination_exit_code(termination),
                    "state": "ABORTED",
                    "abort_reason": "no_progress",
                    "abort_evidence_tail": evidence_tail,
                    "abort_termination": termination,
                }
                state["stdout_handle"].close()
                state["stderr_handle"].close()
                del active[task_id]
                continue

            if now >= state["deadline"]:
                if finish_exited_task(task_id, state, grace_seconds=0.2):
                    continue
                termination = terminate_process_tree(process)
                evidence_tail = combined_log_tail(
                    spec["stdout_path"], spec["stderr_path"], args.log_tail_lines
                )
                append_task_aborted(
                    events_path,
                    spec["task"],
                    args.created_at,
                    "timeout",
                    evidence_tail,
                    termination,
                    process.pid,
                    spec["attempt"],
                )
                outcomes[task_id] = {
                    "return_code": termination_exit_code(termination),
                    "state": "TIMEOUT",
                    "timeout_termination": termination,
                }
                state["stdout_handle"].close()
                state["stderr_handle"].close()
                del active[task_id]
                continue

            if args.heartbeat_interval_seconds > 0 and now - state["last_heartbeat_at"] >= args.heartbeat_interval_seconds:
                state["heartbeat_sequence"] += 1
                state["last_sizes"] = append_worker_heartbeat(
                    events_path,
                    spec["task"],
                    args.created_at,
                    spec["log_dir"],
                    process.pid,
                    spec["attempt"],
                    state["heartbeat_sequence"],
                    spec["stdout_path"],
                    spec["stderr_path"],
                    state["last_sizes"],
                )
                state["last_heartbeat_at"] = now
            else:
                state["last_sizes"] = {"stdout": stdout_size, "stderr": stderr_size}

        if active:
            time.sleep(0.1)
    return outcomes


def run_watch(args, task_ids, timeout):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cmd = [
        sys.executable,
        "-B",
        os.path.join(script_dir, "afc-cal2-arm.py"),
        "--inbox",
        args.inbox,
    ]
    for task_id in task_ids:
        cmd.extend(["--task-id", task_id])
    cmd.extend(["--max-iterations", str(args.watch_max_iterations)])
    cmd.extend(["--poll-interval", str(args.poll_interval)])
    if args.stale_threshold is not None:
        cmd.extend(["--stale-threshold", str(args.stale_threshold)])
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )


def parse_watch_event(stdout):
    text = (stdout or "").strip()
    if not text:
        return {"event": "no_output"}
    try:
        return json.loads(text.splitlines()[-1])
    except json.JSONDecodeError:
        lowered = text.lower()
        if "report_ready" in lowered:
            return {"event": "report_ready"}
        if "report_rejected" in lowered:
            return {"event": "report_rejected"}
        if "stale_alarm" in lowered:
            return {"event": "stale_alarm"}
        if "no_wake" in lowered:
            return {"event": "no_wake"}
        return {"event": "unknown", "text": text[:200]}


def should_run_compat_watch(results):
    return any(result.get("report_exists") for result in results.values())


def contains_approval(log_paths, patterns):
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for path in log_paths:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        for pattern in compiled:
            if pattern.search(text):
                return True
    return False


def locked_scope(task):
    raw = task.get("workspace.locked_files_or_areas", "")
    return [part.strip() for part in re.split(r"[;,]", raw) if part.strip()]


def normalize_locked_scope(scope):
    norm = scope.replace("\\", "/").strip().rstrip("/")
    if norm in {".", "*", "**"}:
        return "__whole_workspace__"
    if norm.startswith("./"):
        norm = norm[2:].rstrip("/")
    if norm in {"", ".", "*", "**"}:
        return "__whole_workspace__"
    return norm


def scopes_overlap(tasks):
    seen = {}
    for task in tasks:
        task_id = task.get("task_id", "")
        for scope in locked_scope(task):
            if scope.lower() in {"read-only", "none"}:
                continue
            norm = normalize_locked_scope(scope)
            for existing, owner in seen.items():
                whole_workspace_overlap = (
                    norm == "__whole_workspace__"
                    or existing == "__whole_workspace__"
                )
                path_overlap = (
                    norm == existing
                    or norm.startswith(existing + "/")
                    or existing.startswith(norm + "/")
                )
                if whole_workspace_overlap or path_overlap:
                    return "locked scope '{}' overlaps task '{}' and '{}'".format(
                        norm, owner, task_id
                    )
            seen[norm] = task_id
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description="CAL-3 headless CLI worker dispatcher.")
    parser.add_argument("--inbox", required=True, help="agent-inbox directory")
    parser.add_argument("--task-id", action="append", required=True)
    parser.add_argument("--recipe-file")
    parser.add_argument(
        "--permission-profile",
        choices=sorted(PROFILES),
        default=None,
    )
    parser.add_argument("--created-at", default=date.today().isoformat())
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--watch-max-iterations", type=int, default=None)
    parser.add_argument("--poll-interval", type=int, default=5)
    parser.add_argument("--stale-threshold", type=int)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--log-tail-lines", type=int, default=20)
    parser.add_argument("--heartbeat-interval-seconds", type=float, default=60)
    parser.add_argument("--abort-on-no-progress-seconds", type=float, default=0)
    parser.add_argument("--abort-on-repeated-failures", type=int, default=0)
    parser.add_argument("--abort-failure-pattern", default=DEFAULT_ABORT_FAILURE_PATTERN)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
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
        print("error: at least one --task-id is required", file=sys.stderr)
        return 1
    if args.max_workers < 1:
        print("error: --max-workers must be >= 1", file=sys.stderr)
        return 1
    if args.heartbeat_interval_seconds < 0:
        print("error: --heartbeat-interval-seconds must be >= 0", file=sys.stderr)
        return 1
    if args.abort_on_no_progress_seconds < 0:
        print("error: --abort-on-no-progress-seconds must be >= 0", file=sys.stderr)
        return 1
    if args.abort_on_repeated_failures < 0:
        print("error: --abort-on-repeated-failures must be >= 0", file=sys.stderr)
        return 1
    if args.abort_on_repeated_failures > 0:
        try:
            re.compile(args.abort_failure_pattern)
        except re.error as exc:
            print("error: invalid --abort-failure-pattern: {}".format(exc), file=sys.stderr)
            return 1
    if len(task_ids) > args.max_workers:
        print("error: task count exceeds --max-workers", file=sys.stderr)
        return 1

    tasks = []
    # Recipe resolution follows the roster source so a marked project override
    # keeps using its own .agent-inbox/invoke-recipes.json even when
    # LOCAL_INVOKE_RECIPES.json also exists in the Skill root. Same path feeds
    # both the gate and the worker launch below.
    _, _roster_source = resolve_roster(args.inbox)
    recipe_file = args.recipe_file or resolve_recipes(args.inbox, roster_source=_roster_source)[0]
    for task_id in task_ids:
        task, err = find_task(args.inbox, task_id)
        if err:
            print("error: {}".format(err), file=sys.stderr)
            return 1
        ok, status = require_usable_roster(
            args.inbox,
            agent_name=task.get("agent_name", ""),
            require_cal3=True,
            recipe_file=recipe_file,
        )
        maybe_warn_roster(status)
        if not ok:
            print(format_roster_block(status), file=sys.stderr)
            return 2
        tasks.append(task)

    recipes_data, err = read_recipes(recipe_file)
    if err:
        print("error: {}".format(err), file=sys.stderr)
        return 1
    profile_name = args.permission_profile or recipes_data.get(
        "default_permission_profile", "cal3-bounded-edit"
    )
    if profile_name not in PROFILES:
        print("error: unknown permission profile: {}".format(profile_name), file=sys.stderr)
        return 1

    launch_specs = []
    for task in tasks:
        task_id = task.get("task_id", "")
        err = check_permission(task, profile_name)
        if err:
            print("error: task {} refused: {}".format(task_id, err), file=sys.stderr)
            return 1
        workspace = resolve_workspace(task)
        if not workspace or not os.path.isdir(workspace):
            print("error: task {} workspace not found: {}".format(task_id, workspace), file=sys.stderr)
            return 1
        report_path = resolve_report_path(task, args.inbox)
        if not report_path or not path_is_within(report_path, args.inbox):
            print("error: task {} report_path must stay inside inbox".format(task_id), file=sys.stderr)
            return 1
        recipe_pair, err = choose_recipe(task, recipes_data)
        if err:
            emit(args, "manual_fallback", task_id, reason=err.replace(" ", "_"))
            return 2
        recipe_id, recipe = recipe_pair
        err = check_cli_capability(task, recipe)
        if err:
            print("error: task {} refused: {}".format(task_id, err), file=sys.stderr)
            return 1
        task_path = resolve_task_path(task)
        argv_list, cwd, env_overrides = build_argv(recipe, profile_name, task, workspace, task_path, report_path)
        if recipe_uses_workspace_sandbox(recipe, profile_name, argv_list) and not path_is_within(report_path, workspace):
            emit(
                args,
                "manual_fallback",
                task_id,
                reason="report_path_outside_workspace",
                report=os.path.relpath(report_path, args.inbox).replace("\\", "/"),
            )
            print(
                "error: task {} report_path must be inside workspace for this CAL-3 recipe; "
                "place .agent-inbox under workspace.path or use a recipe that can write the report path".format(task_id),
                file=sys.stderr,
            )
            return 2
        launch_specs.append({
            "task": task,
            "recipe_id": recipe_id,
            "recipe": recipe,
            "workspace": workspace,
            "report_path": report_path,
            "task_path": task_path,
            "argv": argv_list,
            "cwd": cwd,
            "env_overrides": env_overrides,
        })

    overlap = scopes_overlap(tasks)
    if len(tasks) > 1 and overlap:
        print("error: {}".format(overlap), file=sys.stderr)
        return 1
    args.watch_max_iterations = derive_watch_iterations(args, launch_specs)

    artifact_root = os.path.join(args.inbox, "artifacts", "cal3")
    os.makedirs(artifact_root, exist_ok=True)
    events_path = os.path.join(args.inbox, "events.jsonl")

    if args.max_attempts < 1:
        print("error: --max-attempts must be >= 1", file=sys.stderr)
        return 1
    for spec in launch_specs:
        task = spec["task"]
        task_id = task.get("task_id", "")
        attempts = count_started_events(events_path, task_id)
        if attempts >= args.max_attempts:
            emit(
                args,
                "manual_fallback",
                task_id,
                reason="rework_fuse_tripped",
                attempts=attempts,
                max_attempts=args.max_attempts,
            )
            return 2
        spec["attempt"] = attempts + 1

    processes = {}
    for spec in launch_specs:
        task = spec["task"]
        task_id = task.get("task_id", "")
        log_dir = os.path.join(artifact_root, task_id)
        os.makedirs(log_dir, exist_ok=True)
        stdout_path = os.path.join(log_dir, "stdout.log")
        stderr_path = os.path.join(log_dir, "stderr.log")
        status_path = os.path.join(log_dir, "status.json")
        spec["log_dir"] = log_dir
        spec["stdout_path"] = stdout_path
        spec["stderr_path"] = stderr_path
        spec["status_path"] = status_path
        write_log_readme(log_dir)

        emit(
            args,
            "dispatch",
            task_id,
            recipe=spec["recipe_id"],
            profile=profile_name,
            cwd=spec["cwd"],
        )
        if args.dry_run:
            with open(status_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    {
                        "state": "DRY_RUN",
                        "argv": spec["argv"],
                        "cwd": spec["cwd"],
                        "env_keys": sorted(spec.get("env_overrides", {}).keys()),
                    },
                    handle,
                    indent=2,
                )
                handle.write("\n")
            continue

        append_dispatched(
            events_path,
            task,
            args.created_at,
            profile_name,
            spec["recipe_id"],
            log_dir,
        )
        if source_readonly_required(task, profile_name):
            spec["source_snapshot_before"] = source_snapshot(
                spec["workspace"], args.inbox, spec["report_path"]
            )
        else:
            spec["source_snapshot_before"] = None
        if not profile_allows_commit(profile_name):
            spec["git_history_before"] = git_history_snapshot(spec["workspace"])
        else:
            spec["git_history_before"] = None

        stdout_handle = open(stdout_path, "w", encoding="utf-8", newline="\n", errors="replace")
        stderr_handle = open(stderr_path, "w", encoding="utf-8", newline="\n", errors="replace")
        try:
            process = subprocess.Popen(
                spec["argv"],
                cwd=spec["cwd"],
                env=merged_env(spec.get("env_overrides")),
                stdin=subprocess.DEVNULL,
                stdout=stdout_handle,
                stderr=stderr_handle,
                shell=False,
                text=True,
                **subprocess_startup_kwargs(),
            )
        except OSError as exc:
            stdout_handle.close()
            stderr_handle.close()
            emit(args, "failed", task_id, reason="spawn_failed")
            with open(status_path, "w", encoding="utf-8", newline="\n") as handle:
                json.dump({"state": "FAILED", "error": str(exc)}, handle)
                handle.write("\n")
            return 1
        append_started(
            events_path,
            task,
            args.created_at,
            profile_name,
            spec["recipe_id"],
            log_dir,
            process.pid,
            spec["attempt"],
        )
        emit(args, "started", task_id, session_id="pid:{}".format(process.pid))
        processes[task_id] = (process, stdout_handle, stderr_handle, spec)

    if args.dry_run:
        return 0

    monitor_outcomes = monitor_processes(processes, args, events_path)

    overall_exit = 0
    results = {}
    for task_id, (_process, _stdout_handle, _stderr_handle, spec) in processes.items():
        outcome = monitor_outcomes[task_id]
        report_valid = None
        report_reason = None
        source_violations = []
        commit_violations = []
        timeout_termination = outcome.get("timeout_termination")
        abort_reason = outcome.get("abort_reason")
        abort_evidence_tail = outcome.get("abort_evidence_tail")
        abort_termination = outcome.get("abort_termination")
        return_code = outcome.get("return_code")
        state = outcome.get("state")

        if state == "ABORTED":
            overall_exit = 1
        elif state == "TIMEOUT":
            overall_exit = 1
        elif return_code is None:
            state = "TIMEOUT"
            overall_exit = 1
        elif return_code != 0:
            state = "FAILED"
            overall_exit = 1
        else:
            if os.path.isfile(spec["report_path"]):
                report_valid, report_reason = validate_expected_report(
                    spec["report_path"], task_id, task=spec["task"]
                )
                if report_valid:
                    state = "FINISHED"
                else:
                    state = "INVALID_REPORT"
                    overall_exit = 1
            else:
                state = "NO_REPORT"
                overall_exit = 1
                report_valid = False
                report_reason = "report file not found"

        # Audit source changes on any real process exit, not only exit 0: a
        # worker that mutates tracked files then fails still dirties the
        # workspace, and the coordinator needs that recorded for cleanup.
        # Only a clean exit is upgraded to SOURCE_VIOLATION; a failed exit
        # keeps its failure state but still records the residue. TIMEOUT
        # (return_code is None) is skipped since the process may still write.
        if return_code is not None and source_readonly_required(spec["task"], profile_name):
            after_snapshot = source_snapshot(
                spec["workspace"], args.inbox, spec["report_path"]
            )
            source_violations = source_changes(
                spec.get("source_snapshot_before"), after_snapshot
            )
            if source_violations and return_code == 0:
                state = "SOURCE_VIOLATION"
                overall_exit = 1

        # HEAD/branch movement covers a worker commit (and any push that
        # follows a new commit). It cannot see a push of an already-existing
        # commit, which leaves no local trace; that residual egress is bounded
        # by the recipe network capability + sandbox, not by this guard.
        # Recorded on any real exit; only a clean exit becomes a violation.
        if return_code is not None and not profile_allows_commit(profile_name):
            after_history = git_history_snapshot(spec["workspace"])
            commit_violations = git_history_changes(
                spec.get("git_history_before"), after_history
            )
            if commit_violations and return_code == 0:
                state = "COMMIT_VIOLATION"
                overall_exit = 1

        if state in {"FAILED", "NO_REPORT", "ABORTED", "TIMEOUT"}:
            patterns = spec["recipe"].get("approval_patterns", [])
            if contains_approval([spec["stdout_path"], spec["stderr_path"]], patterns):
                state = "APPROVAL_REQUIRED"
                overall_exit = 2

        report_validation = None
        if os.path.isfile(spec["report_path"]):
            if report_valid is None:
                report_valid, report_reason = validate_expected_report(
                    spec["report_path"], task_id, task=spec["task"]
                )
            report_validation = {
                "result": "pass" if report_valid else "fail",
                "reason": report_reason,
            }

        results[task_id] = {
            "state": state,
            "exit_code": return_code,
            "spec": spec,
            "report_exists": os.path.isfile(spec["report_path"]),
            "report_validation": report_validation,
            "source_violations": source_violations,
            "commit_violations": commit_violations,
            "timeout_termination": timeout_termination,
            "abort_reason": abort_reason,
            "abort_evidence_tail": abort_evidence_tail,
            "abort_termination": abort_termination,
        }

    if should_run_compat_watch(results):
        emit(args, "watch_compat_armed", task_id=",".join(task_ids))
        watcher_timeout = max(5, args.watch_max_iterations * max(args.poll_interval, 0) + 15)
        try:
            watch_result = run_watch(args, task_ids, watcher_timeout)
        except subprocess.TimeoutExpired:
            watch_result = None
            watch_event = {"event": "timeout"}
        else:
            watch_event = parse_watch_event(watch_result.stdout)

        if watch_result is not None:
            watch_log = os.path.join(artifact_root, "watcher-{}.log".format(int(time.time())))
            with open(watch_log, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("stdout:\n")
                handle.write(watch_result.stdout or "")
                handle.write("\nstderr:\n")
                handle.write(watch_result.stderr or "")
        else:
            watch_log = None
    else:
        watch_result = None
        watch_event = {"event": "skipped_no_report"}
        watch_log = None

    emit(
        args,
        "intake_compat",
        task_id=watch_event.get("task_id") or ",".join(task_ids),
        event=watch_event.get("event"),
    )

    for task_id, result in results.items():
        spec = result["spec"]
        state = result["state"]
        return_code = result["exit_code"]
        source_violations = result["source_violations"]
        commit_violations = result["commit_violations"]
        report_validation = result["report_validation"]
        timeout_termination = result.get("timeout_termination")
        abort_reason = result.get("abort_reason")
        abort_evidence_tail = result.get("abort_evidence_tail")
        abort_termination = result.get("abort_termination")
        primary_path = primary_log_path(spec["stdout_path"], spec["stderr_path"])

        # Re-validate after the compat watch so late_report_validation reflects
        # a report that only landed (or changed) during the watcher pass,
        # rather than copying the pre-watch result.
        late_report_validation = report_validation
        if os.path.isfile(spec["report_path"]):
            late_valid, late_reason = validate_expected_report(
                spec["report_path"], task_id, task=spec["task"]
            )
            late_report_validation = {
                "result": "pass" if late_valid else "fail",
                "reason": late_reason,
            }

        status = {
            "state": state,
            "task_id": task_id,
            "exit_code": return_code,
            "report_path": spec["report_path"].replace("\\", "/"),
            "stdout_log": spec["stdout_path"].replace("\\", "/"),
            "stderr_log": spec["stderr_path"].replace("\\", "/"),
            "primary_log_path": primary_path.replace("\\", "/"),
            "watch_event": watch_event,
            "watch_log": watch_log.replace("\\", "/") if watch_log else None,
            "report_validation": report_validation,
            "late_report_validation": late_report_validation,
        }
        if source_violations:
            status["source_violations"] = source_violations
        if commit_violations:
            status["commit_violations"] = commit_violations
        if timeout_termination:
            status["timeout_termination"] = timeout_termination
        if abort_reason:
            status["abort_reason"] = abort_reason
        if abort_evidence_tail is not None:
            status["abort_evidence_tail"] = abort_evidence_tail
        if abort_termination:
            status["abort_termination"] = abort_termination
        if state != "FINISHED":
            status["redacted_stdout_tail"] = tail_redacted(
                spec["stdout_path"], args.log_tail_lines
            )
            status["redacted_stderr_tail"] = tail_redacted(
                spec["stderr_path"], args.log_tail_lines
            )
            status["redacted_primary_log_tail"] = tail_redacted(
                primary_path, args.log_tail_lines
            )
        with open(spec["status_path"], "w", encoding="utf-8", newline="\n") as handle:
            json.dump(status, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        emit(
            args,
            state.lower(),
            task_id,
            exit_code=return_code,
            report=os.path.relpath(spec["report_path"], args.inbox).replace("\\", "/"),
            log=os.path.relpath(spec["log_dir"], args.inbox).replace("\\", "/"),
        )

    return overall_exit


if __name__ == "__main__":
    sys.exit(main())
