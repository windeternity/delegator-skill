#!/usr/bin/env python3
"""Generate a schema-valid task file from a short spec.

Python stdlib only. Reads a YAML-like spec, emits a task file under the
inbox directory, prints a copy-ready handoff instruction, and appends a
TASK_ASSIGNED event to events.jsonl.

Usage:
    python -B scripts/afc-assign.py --spec <SPEC_FILE> --inbox <INBOX_DIR> [--dry-run] [--created-at YYYY-MM-DD] [--handoff-language <TAG>] [--trace-id ID] [--coordinator-thread-id ID] [--coordinator-root-thread-id ID] [--legacy-unrouted]

Exit codes:
    0   task file created (or printed in dry-run mode)
    1   validation failure
"""

import argparse
import json
import os
import re
import sys
import tempfile
import time
from datetime import date

from afc_event import add_event_context, append_event_once
from afc_roster import format_roster_block, maybe_warn_roster, require_usable_roster
from afc_routing import evaluate_route, routing_values_from_spec
from afc_constants import TASK_BUDGET_BYTES


# --- Allowed enum values (must match validate-agent-inbox.py) ---

ROLES = {"coordinator", "planner", "implementer", "reviewer", "smoke", "docs", "research", "other"}
PROTOCOL_MODES = {"full-skill", "worker-brief", "task-only", "manual-paste", "unknown"}
COORD_AUTHORITY = {"yes", "no", "limited"}
STATUSES = {"DRAFT", "ASSIGNED", "RUNNING", "REPORTED", "REVIEWING", "NEEDS_FIX",
            "CLOSED_GO", "CLOSED_PARTIAL", "CLOSED_RED", "BLOCKED", "CANCELLED", "SUPERSEDED"}
WORKSPACE_MODES = {"read_only_shared", "existing_edit_worktree", "dedicated_worktree_required", "manual_worktree_needed"}
MAY_CREATE = {"yes", "no", "ask"}
RUN_COMMANDS = {"none", "read_only", "tests_only", "bounded"}
NETWORK_ACCESS = {"none", "docs_only", "allowed"}
COMMIT_PUSH = {"no", "ask", "approved"}
VALIDATION_TIERS = {"no-test-needed", "targeted-test", "smoke-test", "browser-test", "full-suite", "production-replay"}


_SAFE_NAME_RE = re.compile(r'^[A-Za-z0-9._-]+$')
_SEQUENCE_RE = re.compile(r'^\d+(\.\d+)?$')


def quote_cli_arg(value):
    text = str(value)
    if not text:
        return '""'
    if any(ch.isspace() for ch in text) or '"' in text:
        return '"' + text.replace('"', '\\"') + '"'
    return text


def report_command(report_tool_path, task_filepath):
    return (
        "python -B {tool} --task {task} --verdict GO --changed-file none "
        "--evidence-ref \"TODO: evidence\" --validation-result pass "
        "--summary \"TODO: summary\" --replace"
    ).format(
        tool=quote_cli_arg(report_tool_path),
        task=quote_cli_arg(task_filepath),
    )


def check_command(report_tool_path, task_filepath):
    return "python -B {tool} --task {task} --check".format(
        tool=quote_cli_arg(report_tool_path),
        task=quote_cli_arg(task_filepath),
    )


SEQUENCE_COUNTER_FILENAME = ".seq"
SEQUENCE_LOCK_FILENAME = ".seq.lock"
SEQUENCE_LOCK_TIMEOUT_SECONDS = 5.0
SEQUENCE_LOCK_POLL_SECONDS = 0.02


def _read_sequence_counter(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read().strip()
    except OSError:
        return 0
    try:
        value = int(text)
    except (TypeError, ValueError):
        return 0
    return value if value >= 0 else 0


def peek_sequence(inbox_dir):
    """Return the next task sequence number without consuming it.

    The counter lives at ``<inbox>/.seq`` as a single integer: an O(1) read,
    independent of inbox size, and never archived. Peeking lets the marker be
    embedded in the task/handoff before we know the dispatch will succeed; the
    Dry-run callers may use this advisory value without consuming it. Real
    assignments must use ``reserve_sequence`` so concurrent processes cannot
    receive the same marker.
    """
    counter_path = os.path.join(inbox_dir, SEQUENCE_COUNTER_FILENAME)
    return _read_sequence_counter(counter_path) + 1


def _process_is_alive(pid):
    if pid <= 0:
        return False
    if os.name == "nt":
        # Windows os.kill(pid, 0) terminates the target process instead of
        # performing the POSIX existence probe. Query a process handle instead.
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.OpenProcess.restype = ctypes.c_void_p
            kernel32.OpenProcess.argtypes = (
                ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32
            )
            kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if not handle:
                # Access denied proves that the process exists even though it
                # cannot be queried by this coordinator.
                return kernel32.GetLastError() == 5
            kernel32.CloseHandle(handle)
            return True
        except (AttributeError, OSError):
            return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _reclaim_abandoned_sequence_lock(lock_path):
    """Remove a dead-owner lock only if it is unchanged since inspection."""
    try:
        before = os.stat(lock_path)
        with open(lock_path, "r", encoding="ascii") as handle:
            raw_pid = handle.read().strip()
    except (OSError, UnicodeError):
        return False

    try:
        owner_pid = int(raw_pid)
    except ValueError:
        owner_pid = 0

    if owner_pid and _process_is_alive(owner_pid):
        return False
    if not owner_pid and time.time() - before.st_mtime < SEQUENCE_LOCK_TIMEOUT_SECONDS:
        return False

    try:
        after = os.stat(lock_path)
        fingerprint_before = (before.st_ino, before.st_size, before.st_mtime_ns)
        fingerprint_after = (after.st_ino, after.st_size, after.st_mtime_ns)
        if fingerprint_before != fingerprint_after:
            return False
        os.remove(lock_path)
        return True
    except OSError:
        return False


def _acquire_sequence_lock(inbox_dir):
    lock_path = os.path.join(inbox_dir, SEQUENCE_LOCK_FILENAME)
    deadline = time.monotonic() + SEQUENCE_LOCK_TIMEOUT_SECONDS
    while True:
        descriptor = None
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, "{}\n".format(os.getpid()).encode("ascii"))
            return descriptor, lock_path
        except FileExistsError:
            if time.monotonic() >= deadline:
                # Inspect only after the normal wait expires. On Windows,
                # repeatedly opening the live lock for inspection can prevent
                # its owner from deleting it during release.
                if _reclaim_abandoned_sequence_lock(lock_path):
                    deadline = time.monotonic() + SEQUENCE_LOCK_TIMEOUT_SECONDS
                    continue
                print(
                    "warning: timed out waiting for sequence lock {}".format(lock_path),
                    file=sys.stderr,
                )
                return None, lock_path
            time.sleep(SEQUENCE_LOCK_POLL_SECONDS)
        except OSError as exc:
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError:
                    pass
                try:
                    os.remove(lock_path)
                except OSError:
                    pass
            print(
                "warning: could not acquire sequence lock {}: {}".format(
                    lock_path, exc
                ),
                file=sys.stderr,
            )
            return None, lock_path


def _release_sequence_lock(descriptor, lock_path):
    if descriptor is not None:
        try:
            os.close(descriptor)
        except OSError:
            pass
    try:
        os.remove(lock_path)
    except OSError:
        pass


def _persist_sequence_unlocked(inbox_dir, value):
    counter_path = os.path.join(inbox_dir, SEQUENCE_COUNTER_FILENAME)
    temp = None
    try:
        descriptor, temp = tempfile.mkstemp(
            prefix=SEQUENCE_COUNTER_FILENAME + ".",
            suffix=".tmp",
            dir=inbox_dir,
            text=True,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("{}\n".format(value))
        os.replace(temp, counter_path)
        temp = None
    except OSError as exc:
        if temp:
            try:
                os.remove(temp)
            except OSError:
                pass
        print(
            "warning: could not update sequence counter {}: {}".format(
                counter_path, exc
            ),
            file=sys.stderr,
        )
        return False
    return True


def commit_sequence(inbox_dir, value):
    """Persist exactly the next sequence value under an exclusive lock."""
    descriptor, lock_path = _acquire_sequence_lock(inbox_dir)
    if descriptor is None:
        return False
    try:
        current = _read_sequence_counter(
            os.path.join(inbox_dir, SEQUENCE_COUNTER_FILENAME)
        )
        if value != current + 1:
            print(
                "warning: sequence {} is stale; next value is {}".format(
                    value, current + 1
                ),
                file=sys.stderr,
            )
            return False
        return _persist_sequence_unlocked(inbox_dir, value)
    finally:
        _release_sequence_lock(descriptor, lock_path)


def reserve_sequence(inbox_dir):
    """Atomically reserve and persist the next unique sequence number."""
    descriptor, lock_path = _acquire_sequence_lock(inbox_dir)
    if descriptor is None:
        return None
    try:
        value = _read_sequence_counter(
            os.path.join(inbox_dir, SEQUENCE_COUNTER_FILENAME)
        ) + 1
        if not _persist_sequence_unlocked(inbox_dir, value):
            return None
        return value
    finally:
        _release_sequence_lock(descriptor, lock_path)


def completion_marker_from_spec(spec):
    sequence = spec.get("handoff.sequence", "")
    if not sequence:
        return ""
    lang = (
        spec.get("handoff.language_cli") or spec.get("handoff.language") or "en"
    ).strip().lower()
    if lang.startswith("zh"):
        return "完成任务：#{}".format(sequence)
    return "Completed task: #{}".format(sequence)


def _validate_date(value, field_name):
    """Validate YYYY-MM-DD format. Returns error string or None."""
    if not value:
        return None  # empty is handled by required-field check
    try:
        date.fromisoformat(value)
    except (ValueError, TypeError):
        return f"{field_name} is not a valid YYYY-MM-DD date: {value}"
    return None


def _validate_safe_name(value, field_name):
    """Reject path separators and unsafe characters in identifiers."""
    if not value:
        return None
    if not _SAFE_NAME_RE.match(value):
        return f"{field_name} contains unsafe characters: {value!r} (only A-Za-z0-9._- allowed)"
    return None


def parse_spec(filepath):
    """Parse a simple YAML-like spec file. Returns (dict, error)."""
    try:
        with open(filepath, "r", encoding="utf-8-sig") as f:
            content = f.read()
    except OSError as exc:
        return None, f"could not read spec: {exc}"

    data = {}
    current_top_key = None
    frontmatter_markers = 0
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "---":
            frontmatter_markers += 1
            if frontmatter_markers >= 2:
                break
            continue
        if ":" not in line:
            return None, f"malformed spec line: {raw_line}"
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            return None, f"empty key in spec: {raw_line}"

        indent = len(raw_line) - len(raw_line.lstrip())
        if indent > 0 and current_top_key:
            nested_key = f"{current_top_key}.{key}"
            data[nested_key] = value
            continue

        data[key] = value
        current_top_key = key if value == "" else None

    return data, None


def validate_spec(data):
    """Validate required fields and enum values. Returns list of errors."""
    errors = []

    # Required top-level fields
    for field in ("task_id", "agent_name", "role", "protocol_mode",
                  "coordinator_authority", "validation_tier", "report_path",
                  "purpose", "created_at"):
        if not data.get(field):
            errors.append(f"missing required field: {field}")

    # Required nested fields
    for field in ("workspace.mode", "workspace.path", "workspace.may_create_worktree"):
        if not data.get(field):
            errors.append(f"missing required field: {field}")

    if "acceptance" in data and not data.get("acceptance_criteria"):
        errors.append(
            "unknown spec key: acceptance; use acceptance_criteria"
        )
    acceptance_items = [
        item.strip()
        for item in data.get("acceptance_criteria", "").split(";")
        if item.strip()
    ]
    if not acceptance_items:
        errors.append("missing or empty field: acceptance_criteria")

    # Enum validation
    v = data.get("role", "")
    if v and v not in ROLES:
        errors.append(f"invalid role: {v}")

    v = data.get("protocol_mode", "")
    if v and v not in PROTOCOL_MODES:
        errors.append(f"invalid protocol_mode: {v}")

    v = data.get("coordinator_authority", "")
    if v and v not in COORD_AUTHORITY:
        errors.append(f"invalid coordinator_authority: {v}")

    v = data.get("workspace.mode", "")
    if v and v not in WORKSPACE_MODES:
        errors.append(f"invalid workspace.mode: {v}")

    v = data.get("workspace.may_create_worktree", "")
    if v and v not in MAY_CREATE:
        errors.append(f"invalid workspace.may_create_worktree: {v}")

    v = data.get("permission_scope.run_commands", "")
    if v and v not in RUN_COMMANDS:
        errors.append(f"invalid permission_scope.run_commands: {v}")

    v = data.get("permission_scope.network_access", "")
    if v and v not in NETWORK_ACCESS:
        errors.append(f"invalid permission_scope.network_access: {v}")

    v = data.get("permission_scope.commit_push", "")
    if v and v not in COMMIT_PUSH:
        errors.append(f"invalid permission_scope.commit_push: {v}")

    v = data.get("validation_tier", "")
    if v and v not in VALIDATION_TIERS:
        errors.append(f"invalid validation_tier: {v}")

    vc = str(data.get("validation_command", "") or "")
    if "\n" in vc or "\r" in vc:
        errors.append("validation_command must be a single line")

    # Coordinator authority constraint
    role = data.get("role", "")
    protocol = data.get("protocol_mode", "")
    coord = data.get("coordinator_authority", "")
    if coord == "yes" and role != "coordinator":
        errors.append("coordinator_authority: yes requires role: coordinator")
    if coord == "yes" and protocol != "full-skill":
        errors.append("coordinator_authority: yes requires protocol_mode: full-skill")

    # Workspace constraints
    ws_mode = data.get("workspace.mode", "")
    modify = data.get("permission_scope.modify_source", "no")
    may_create = data.get("workspace.may_create_worktree", "")
    if ws_mode == "read_only_shared" and modify == "yes":
        errors.append("read_only_shared workspace cannot allow modify_source")
    if ws_mode == "manual_worktree_needed" and may_create == "yes":
        errors.append("manual_worktree_needed cannot have may_create_worktree: yes")

    # Date format validation
    for field in ("created_at",):
        err = _validate_date(data.get(field, ""), field)
        if err:
            errors.append(err)

    # Identifier safety (no path separators or unsafe chars)
    for field in ("task_id", "agent_name", "trace_id",
                  "coordinator_thread_id", "coordinator_root_thread_id"):
        err = _validate_safe_name(data.get(field, ""), field)
        if err:
            errors.append(err)

    # handoff.sequence validation (optional)
    seq = data.get("handoff.sequence", "")
    if seq:
        if not _SEQUENCE_RE.match(seq):
            errors.append(
                f"handoff.sequence must be an integer or integer.integer "
                f"(e.g. 37 or 32.1), got: {seq!r}"
            )

    return errors


def generate_task_content(spec):
    """Generate the full task Markdown content from a validated spec."""
    task_id = spec["task_id"]
    agent_name = spec["agent_name"]
    role = spec["role"]
    protocol_mode = spec["protocol_mode"]
    coord_auth = spec["coordinator_authority"]
    ws_mode = spec["workspace.mode"]
    ws_path = spec["workspace.path"]
    may_create = spec["workspace.may_create_worktree"]
    validation_tier = spec["validation_tier"]
    validation_command = str(spec.get("validation_command") or "").strip()
    report_path = spec["report_path"]
    created_at = spec["created_at"]
    trace_id = spec.get("trace_id", "")
    coordinator_thread_id = spec.get("coordinator_thread_id", "")
    coordinator_root_thread_id = spec.get("coordinator_root_thread_id", "")
    routing_decision = spec.get("_routing_decision", "")
    purpose = spec.get("purpose", "")
    branch = spec.get("workspace.branch", "")
    base = spec.get("workspace.base", "")
    locked = spec.get("workspace.locked_files_or_areas", "")
    modify_source = spec.get("permission_scope.modify_source", "no")
    run_commands = spec.get("permission_scope.run_commands", "none")
    network_access = spec.get("permission_scope.network_access", "none")
    commit_push = spec.get("permission_scope.commit_push", "no")
    non_goals = spec.get("non_goals", "")
    acceptance = spec.get("acceptance_criteria", "")
    evidence = spec.get("evidence_to_report", "")
    read_first = spec.get("read_first", "")
    report_tool_path = spec.get("_report_tool_path", "")
    preferred = spec.get("model_hint.preferred", "")
    reason = spec.get("model_hint.reason", "")
    fallback = spec.get("model_hint.fallback", "")
    has_edit_scope = modify_source == "yes" or bool(locked)
    marker = completion_marker_from_spec(spec)

    # Build frontmatter
    fm_lines = [
        "---",
        "schema: agent-file-coordination/task",
        "schema_version: 0.1.0",
        f"task_id: {task_id}",
        f"trace_id: {trace_id}",
        f"agent_name: {agent_name}",
        f"role: {role}",
        f"protocol_mode: {protocol_mode}",
        f"coordinator_authority: {coord_auth}",
        f"routing_decision: {routing_decision}",
        "status: ASSIGNED",
        "permission_scope:",
        "  read_files: yes",
        "  write_task_files: no",
        "  write_reports: yes",
        f"  modify_source: {modify_source}",
        f"  run_commands: {run_commands}",
        f"  network_access: {network_access}",
        f"  commit_push: {commit_push}",
        "  destructive_actions: no",
        "workspace:",
        f"  mode: {ws_mode}",
        f"  path: {ws_path}",
        f"  may_create_worktree: {may_create}",
    ]
    if branch:
        fm_lines.append(f"  branch: {branch}")
    if base:
        fm_lines.append(f"  base: {base}")
    if locked:
        fm_lines.append(f"  locked_files_or_areas: {locked}")
    if coordinator_thread_id:
        fm_lines.append(f"coordinator_thread_id: {coordinator_thread_id}")
    if coordinator_root_thread_id:
        fm_lines.append(f"coordinator_root_thread_id: {coordinator_root_thread_id}")
    if marker:
        fm_lines.append(f"completion_marker: {marker}")
    fm_lines.append(f"validation_tier: {validation_tier}")
    if validation_command:
        fm_lines.append(f"validation_command: {validation_command}")
    fm_lines.extend([
        f"report_path: {report_path}",
        f"report_tool: {report_tool_path}",
        f"created_at: {created_at}",
        "---",
    ])

    # Keep the body compact. Frontmatter is the canonical permission and
    # workspace source, so repeating those fields wastes coordinator context.
    body_lines = [
        "",
        f"# Task - {agent_name} {task_id}",
        "",
        "## Role Boundary",
        "Worker only: no reassign, scope expansion, or final verdict. Put follow-up in the report.",
        "",
    ]

    # Model hint (optional)
    if preferred or reason or fallback:
        body_lines.extend([
            "## Model / Tool / Capability Hint",
            f"- preferred: {preferred or '(not specified)'}",
            f"- reason: {reason or '(not specified)'}",
            f"- fallback: {fallback or '(not specified)'}",
            "",
        ])

    body_lines.extend([
        "## Purpose",
        purpose,
        "",
        "## Non-Goals",
    ])
    if non_goals:
        for ng in non_goals.split(";"):
            ng = ng.strip()
            if ng:
                body_lines.append(f"- {ng}")
    else:
        body_lines.append("- (none specified)")
    body_lines.append("")

    # Release Operations Scope (only when commit_push is approved)
    if commit_push == "approved":
        release_ops_lines = [
            "## Release Operations Scope",
            f"- branch: {branch or '(see workspace)'}",
            "- allowed: commit,push,PR",
            f"- allowlist: {locked or '(see locked_files_or_areas)'}",
            "",
        ]
        body_lines.extend(release_ops_lines)

    # Read first
    body_lines.append("## Read First")
    if read_first:
        for i, item in enumerate(read_first.split(";"), 1):
            item = item.strip()
            if item:
                body_lines.append(f"{i}. {item}")
    else:
        body_lines.append("1. (none specified)")
    body_lines.append("")

    body_lines.extend([
        "## Acceptance Criteria",
    ])
    if acceptance:
        for ac in acceptance.split(";"):
            ac = ac.strip()
            if ac:
                body_lines.append(f"- {ac}")
    else:
        body_lines.append("- (none specified)")
    body_lines.extend([
        "",
        "## Evidence To Report",
        evidence or "(not specified)",
        "",
        "## Finish",
    ])
    if has_edit_scope:
        body_lines.append(
            "- Check `git diff --name-only`; only locked paths."
        )
    body_lines.extend([
        "- Report: `python -B <report_tool> --task <this_task> --verdict GO --changed-file <p> --evidence-ref x --validation-result pass --summary x --replace`.",
        "",
    ])

    return "\n".join(fm_lines) + "\n".join(body_lines)


def generate_handoff(spec, task_filepath, inbox_dir):
    """Generate the copy-ready handoff instruction.

    Language selection order:
    1. --handoff-language CLI flag (injected into spec as handoff.language_cli)
    2. handoff.language in spec
    3. Default: "en"

    For built-in languages (en, zh), generates localized handoff directly.
    For other languages, requires handoff.template in spec with variables:
      {agent_name}, {ws_path}, {inbox_dir}, {task_filepath}, {report_path}
    Returns (handoff_text, error_string). On success error is None.
    If a language is unsupported and no template is provided, returns (None, error).
    """
    agent_name = spec["agent_name"]
    ws_path = spec["workspace.path"]
    may_create = spec.get("workspace.may_create_worktree", "no")
    report_path = spec["report_path"]
    branch = spec.get("workspace.branch", "")
    base = spec.get("workspace.base", "")
    modify_source = spec.get("permission_scope.modify_source", "no")
    commit_push = spec.get("permission_scope.commit_push", "no")
    is_read_only = (may_create == "no" and modify_source == "no")

    # CLI overrides spec
    lang = spec.get("handoff.language_cli") or spec.get("handoff.language") or "en"
    lang = lang.strip().lower()

    # Completion marker (optional)
    sequence = spec.get("handoff.sequence", "")
    report_tool_path = spec.get("_report_tool_path", "")
    finish_command = report_command(report_tool_path, task_filepath)
    verify_command = check_command(report_tool_path, task_filepath)
    validation_command = str(spec.get("validation_command") or "").strip()

    if lang.startswith("zh"):
        lines = [f"你是 {agent_name}。"]
        if may_create == "yes" and branch and base:
            lines.append(f"运行以下命令创建 worktree：")
            lines.append(f'git worktree add "{ws_path}" -b {branch} {base}')
        elif may_create != "yes":
            lines.append(f"把这个现有 worktree 作为项目打开：{ws_path}。")
            lines.append(f"不要把 {inbox_dir} 作为项目打开。")
            lines.append("不要新建 worktree。")
        if is_read_only:
            lines.append("主仓只读，不要切换分支。")
        lines.append("接手时主仓在哪个分支、是否干净，任务结束前必须保持原样。")
        if commit_push == "approved":
            lines.append(f"读取 {task_filepath}，只在 Permission Scope 内执行该任务，并把回执写到指定 Report Path ({report_path})。遵循任务中的 Release Operations Scope 进行 commit/push 操作。")
        else:
            lines.append(f"读取 {task_filepath}，只在 Permission Scope 内执行该任务，并把回执写到指定 Report Path ({report_path})。不要 commit/push。")
        if validation_command:
            lines.append("写回执之前，先运行这条代码门禁，必须退出码为 0；失败就改代码（不是改回执）再重跑：")
            lines.append(validation_command)
            lines.append("把该命令、退出码和最多 10 行输出尾部写进 evidence。")
        lines.append("不要手写 Markdown 回执；使用这条报告命令并按实际情况替换 TODO 值：")
        lines.append(finish_command)
        lines.append("回复前必须运行这条自检命令，看到 CHECK: PASS 才算完成；FAIL 就按提示改：")
        lines.append(verify_command)
        if sequence:
            lines.append(f"最终回复最后一行必须是：完成任务：#{sequence}")
            lines.append(f"完成任务：#{sequence}")
        return "\n".join(lines), None
    elif lang == "en":
        lines = [f"You are {agent_name}."]
        if may_create == "yes" and branch and base:
            lines.append(f"Run this command to create a worktree:")
            lines.append(f'git worktree add "{ws_path}" -b {branch} {base}')
        elif may_create != "yes":
            lines.append(f"Open this existing worktree as the project: {ws_path}.")
            lines.append(f"Do not open {inbox_dir} as the project.")
            lines.append("Do not create another worktree.")
        if is_read_only:
            lines.append("Primary checkout is read-only. Do not switch branches.")
        lines.append("Leave the primary checkout on the branch and cleanliness you found it in.")
        if commit_push == "approved":
            lines.append(f"Read {task_filepath}. Execute only this task within its Permission Scope and write your report to the specified Report Path ({report_path}). Follow the task's Release Operations Scope for commit/push operations.")
        else:
            lines.append(f"Read {task_filepath}. Execute only this task within its Permission Scope and write your report to the specified Report Path ({report_path}). Do not commit or push.")
        if validation_command:
            lines.append("Before writing the report, run this code gate; it must exit 0. If it fails, fix the code (not the report) and re-run it:")
            lines.append(validation_command)
            lines.append("Record the command, its exit code, and up to 10 lines of output tail in your evidence.")
        lines.append("Do not hand-write the Markdown report; use this report command and replace TODO values with real values:")
        lines.append(finish_command)
        lines.append("Before replying, you must run this self-check and see 'CHECK: PASS'; if it prints FAIL, follow the hint and fix it:")
        lines.append(verify_command)
        if sequence:
            lines.append(f"Final line of your user-facing completion reply must be: Completed task: #{sequence}")
            lines.append(f"Completed task: #{sequence}")
        return "\n".join(lines), None
    else:
        # Unsupported language: require handoff.template
        template = spec.get("handoff.template")
        if not template:
            return None, (
                f"language '{lang}' is not built in and no handoff.template was provided. "
                f"Coordinator must manually localize the handoff in the user's language. "
                f"Do not forward an English fallback to the worker."
            )
        # Substitute template variables
        handoff = template.format(
            agent_name=agent_name,
            ws_path=ws_path,
            inbox_dir=inbox_dir,
            task_filepath=task_filepath,
            report_path=report_path,
            sequence=sequence,
        )
        return handoff, None


def resolve_inbox_report_path(inbox_dir, report_path):
    if os.path.isabs(report_path):
        return os.path.abspath(report_path)
    normalized = report_path.replace("\\", "/")
    if (
        os.path.basename(inbox_dir).lower() == ".agent-inbox"
        and normalized.startswith(".agent-inbox/")
    ):
        return os.path.abspath(os.path.join(os.path.dirname(inbox_dir), report_path))
    return os.path.abspath(os.path.join(inbox_dir, report_path))


def path_is_within(path, parent):
    try:
        return os.path.commonpath(
            [os.path.normcase(path), os.path.normcase(parent)]
        ) == os.path.normcase(parent)
    except ValueError:
        return False


def make_event(task_id, agent_name, status, created_at, summary, source):
    """Build a TASK_ASSIGNED event dict."""
    event = {
        "schema": "agent-file-coordination/event",
        "schema_version": "0.1.0",
        "event_id": f"evt-{task_id}-assigned",
        "event_type": "TASK_ASSIGNED",
        "task_id": task_id,
        "agent_name": agent_name,
        "status": status,
        "created_at": created_at,
        "summary": summary,
    }
    if source.get("_routing_decision"):
        event["routing_decision"] = source["_routing_decision"]
    if source.get("_routing_reason_codes"):
        event["routing_reason_codes"] = source["_routing_reason_codes"]
    if source.get("completion_marker"):
        event["completion_marker"] = source["completion_marker"]
    return add_event_context(event, source, "assignment")


def make_dispatched_event(task_id, agent_name, created_at, source):
    """Build a TASK_DISPATCHED event dict."""
    event = {
        "schema": "agent-file-coordination/event",
        "schema_version": "0.1.0",
        "event_id": f"evt-{task_id}-dispatched",
        "event_type": "TASK_DISPATCHED",
        "task_id": task_id,
        "agent_name": agent_name,
        "created_at": created_at,
        "summary": f"Handoff dispatched to {agent_name}.",
    }
    if source.get("completion_marker"):
        event["completion_marker"] = source["completion_marker"]
    return add_event_context(event, source, "dispatch")


def confirm_dispatch(inbox_dir, task_id, agent_name, created_at, dry_run=False):
    """Append a TASK_DISPATCHED event for an existing task.

    This is a post-delivery confirmation: run only after the handoff has been
    actually delivered to the worker. Idempotent — refuses duplicate confirmation.

    Returns 0 on success, 1 on error.
    """
    # Find the task file to verify it exists and get agent_name
    task_pattern = f"task-{agent_name}-{task_id}.md"
    task_filepath = os.path.join(inbox_dir, task_pattern)
    if not os.path.isfile(task_filepath):
        # Try to find by task_id in any task file
        import glob
        for f in glob.glob(os.path.join(inbox_dir, "task-*.md")):
            data, err = parse_spec(f)
            if data and data.get("task_id") == task_id:
                task_filepath = f
                agent_name = data.get("agent_name", agent_name)
                break
        else:
            print(f"error: no task file found for task_id '{task_id}'", file=sys.stderr)
            return 1

    task_data, task_err = parse_spec(task_filepath)
    if task_err:
        print(f"error: could not read task metadata: {task_err}", file=sys.stderr)
        return 1
    agent_name = task_data.get("agent_name", agent_name)
    ok, status = require_usable_roster(inbox_dir, agent_name=agent_name)
    maybe_warn_roster(status)
    if not ok:
        print(format_roster_block(status), file=sys.stderr)
        return 1

    # Check for existing TASK_DISPATCHED event (idempotent)
    events_path = os.path.join(inbox_dir, "events.jsonl")
    if os.path.isfile(events_path):
        try:
            with open(events_path, "r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                        if (evt.get("event_type") == "TASK_DISPATCHED" and
                                evt.get("task_id") == task_id):
                            print(f"Task '{task_id}' already dispatched (idempotent).")
                            return 0
                    except json.JSONDecodeError:
                        continue
        except OSError:
            pass

    if dry_run:
        print(f"Would append TASK_DISPATCHED event for task '{task_id}' to {events_path}")
        return 0

    # Append TASK_DISPATCHED event
    dispatched_event = make_dispatched_event(
        task_id, agent_name, created_at, task_data
    )
    try:
        append_event_once(events_path, dispatched_event)
    except OSError as exc:
        print(f"error: failed to append dispatched event to events.jsonl: {exc}", file=sys.stderr)
        return 1

    print(f"Dispatch confirmed for task '{task_id}'.")
    print(f"Appended TASK_DISPATCHED event to {events_path}")
    return 0


def main():
    # Parse arguments. allow_abbrev=False preserves the previous exact
    # long-flag matching (no prefix abbreviation); --help now works, and
    # usage errors exit 2 (the argparse convention other afc-* scripts use).
    #
    # --confirm-dispatch / --confirm-dispatch-agent take task_id / agent_name
    # values that _SAFE_NAME_RE permits to start with '-'. argparse treats a
    # '-'-prefixed token as an option rather than a value, so pull these two
    # options out of argv first (both "--opt value" and "--opt=value" forms,
    # matching the previous manual parser) and hand the rest to argparse.
    # They stay registered below for --help discoverability.
    argv = sys.argv[1:]
    confirm_dispatch_id = None
    confirm_dispatch_agent = None
    rest = []
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--confirm-dispatch" and i + 1 < len(argv):
            confirm_dispatch_id = argv[i + 1]
            i += 2
            continue
        if tok.startswith("--confirm-dispatch="):
            confirm_dispatch_id = tok[len("--confirm-dispatch="):]
            i += 1
            continue
        if tok == "--confirm-dispatch-agent" and i + 1 < len(argv):
            confirm_dispatch_agent = argv[i + 1]
            i += 2
            continue
        if tok.startswith("--confirm-dispatch-agent="):
            confirm_dispatch_agent = tok[len("--confirm-dispatch-agent="):]
            i += 1
            continue
        rest.append(tok)
        i += 1

    parser = argparse.ArgumentParser(
        prog="afc-assign.py",
        description="Generate a schema-valid task file from a routing spec.",
        allow_abbrev=False,
    )
    parser.add_argument("--dry-run", action="store_true", help="validate without writing task files")
    parser.add_argument("--confirm-dispatch", metavar="TASK_ID")
    parser.add_argument("--confirm-dispatch-agent", metavar="AGENT_NAME")
    parser.add_argument("--spec", metavar="FILE")
    parser.add_argument("--inbox", metavar="DIR")
    parser.add_argument("--created-at", metavar="YYYY-MM-DD")
    parser.add_argument("--handoff-language", metavar="LANG")
    parser.add_argument("--trace-id", metavar="ID")
    parser.add_argument("--coordinator-thread-id", metavar="ID")
    parser.add_argument("--coordinator-root-thread-id", metavar="ID")
    parser.add_argument("--legacy-unrouted", action="store_true", help="generate unrouted tasks (legacy; not for new work)")
    args = parser.parse_args(rest)

    dry_run = args.dry_run
    created_at = args.created_at
    spec_path = args.spec
    inbox_dir = args.inbox
    handoff_language = args.handoff_language
    trace_id = args.trace_id
    coordinator_thread_id = args.coordinator_thread_id
    coordinator_root_thread_id = args.coordinator_root_thread_id
    legacy_unrouted = args.legacy_unrouted

    # Handle --confirm-dispatch mode
    if confirm_dispatch_id:
        if not inbox_dir:
            print("error: --inbox is required with --confirm-dispatch", file=sys.stderr)
            return 1
        if not os.path.isdir(inbox_dir):
            print(f"error: inbox directory not found: {inbox_dir}", file=sys.stderr)
            return 1
        if created_at is None:
            created_at = date.today().isoformat()
        agent = confirm_dispatch_agent or "unknown"
        return confirm_dispatch(inbox_dir, confirm_dispatch_id, agent, created_at, dry_run)

    # Validate required args for task generation
    if not spec_path:
        print("error: --spec is required", file=sys.stderr)
        return 1
    if not inbox_dir:
        print("error: --inbox is required", file=sys.stderr)
        return 1

    if not os.path.isfile(spec_path):
        print(f"error: spec file not found: {spec_path}", file=sys.stderr)
        return 1
    if not os.path.isdir(inbox_dir):
        print(f"error: inbox directory not found: {inbox_dir}", file=sys.stderr)
        return 1

    if created_at is None:
        created_at = date.today().isoformat()

    # Parse spec
    spec, err = parse_spec(spec_path)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return 1

    # Inject created_at if not in spec
    if not spec.get("created_at"):
        spec["created_at"] = created_at
    spec["trace_id"] = (
        trace_id or spec.get("trace_id") or os.environ.get("AFC_TRACE_ID")
        or spec.get("task_id", "")
    )
    thread_id = (
        coordinator_thread_id or spec.get("coordinator_thread_id")
        or os.environ.get("CODEX_THREAD_ID")
    )
    root_thread_id = (
        coordinator_root_thread_id or spec.get("coordinator_root_thread_id")
        or os.environ.get("CODEX_ROOT_THREAD_ID")
    )
    if thread_id:
        spec["coordinator_thread_id"] = thread_id
    if root_thread_id:
        spec["coordinator_root_thread_id"] = root_thread_id

    # Validate
    errors = validate_spec(spec)
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1

    routing_values = routing_values_from_spec(spec)
    if not routing_values:
        if not legacy_unrouted:
            print(
                "error: routing evidence is required; run afc-route.py and add "
                "routing.* fields to the spec",
                file=sys.stderr,
            )
            print(
                "error: --legacy-unrouted is migration-only and must not be used "
                "for new coordination work",
                file=sys.stderr,
            )
            return 1
        routing = {
            "decision": "FULL",
            "reason_codes": ["LEGACY_UNROUTED"],
            "reasons": ["legacy migration override"],
        }
        print(
            "WARN: accepting an unrouted assignment through --legacy-unrouted",
            file=sys.stderr,
        )
    else:
        routing = evaluate_route(routing_values)
        if routing["decision"] != "FULL":
            print(
                "error: full assignment refused; route decision is {}".format(
                    routing["decision"]
                ),
                file=sys.stderr,
            )
            for reason in routing["reasons"]:
                print("error: {}".format(reason), file=sys.stderr)
            if routing["decision"] == "LITE":
                print("error: use afc-lite.py instead", file=sys.stderr)
            return 1
    spec["_routing_decision"] = routing["decision"]
    spec["_routing_reason_codes"] = ",".join(routing.get("reason_codes", []))
    report_path = resolve_inbox_report_path(inbox_dir, spec["report_path"])
    inbox_root = os.path.abspath(inbox_dir)
    if not path_is_within(report_path, inbox_root):
        print(
            "error: report_path must stay inside the assigned inbox",
            file=sys.stderr,
        )
        return 1
    spec["report_path"] = report_path.replace("\\", "/")

    task_id = spec["task_id"]
    agent_name = spec["agent_name"]

    ok, status = require_usable_roster(inbox_dir, agent_name=agent_name)
    maybe_warn_roster(status)
    if not ok:
        print(format_roster_block(status), file=sys.stderr)
        return 1

    # CLI --handoff-language overrides spec handoff.language
    if handoff_language:
        spec["handoff.language_cli"] = handoff_language

    # Determine output path
    task_filename = f"task-{agent_name}-{task_id}.md"
    task_filepath = os.path.join(inbox_dir, task_filename)
    spec["_report_tool_path"] = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "afc-report.py")
    )
    # Check for existing file
    if os.path.exists(task_filepath):
        print(f"error: task file already exists: {task_filepath}", file=sys.stderr)
        return 1

    # Auto-allocate a task sequence when the coordinator did not supply one.
    # First use an advisory value so every fallible content/handoff validation
    # completes without mutating the counter. Real assignments reserve the
    # final value immediately before writing artifacts.
    pending_sequence = None
    auto_sequence = not str(spec.get("handoff.sequence") or "").strip()
    if auto_sequence:
        pending_sequence = peek_sequence(inbox_dir)
        spec["handoff.sequence"] = str(pending_sequence)

    marker = completion_marker_from_spec(spec)
    if marker:
        spec["completion_marker"] = marker

    # Generate content
    content = generate_task_content(spec)
    content_size = len(content.encode("utf-8"))
    if content_size > TASK_BUDGET_BYTES:
        print(
            "error: generated task is {} bytes; hard budget is {} bytes. "
            "Move context to referenced files or split the task.".format(
                content_size, TASK_BUDGET_BYTES
            ),
            file=sys.stderr,
        )
        return 1
    handoff, handoff_err = generate_handoff(spec, task_filepath, inbox_dir)

    if handoff_err:
        print(f"error: {handoff_err}", file=sys.stderr)
        return 1

    if dry_run:
        print(f"Would write: {task_filepath}")
        print()
        print(content)
        print()
        print("--- Handoff ---")
        print(handoff)
        return 0

    if auto_sequence:
        pending_sequence = reserve_sequence(inbox_dir)
        if pending_sequence is None:
            print("error: could not reserve a unique handoff sequence", file=sys.stderr)
            return 1
        spec["handoff.sequence"] = str(pending_sequence)
        marker = completion_marker_from_spec(spec)
        if marker:
            spec["completion_marker"] = marker
        content = generate_task_content(spec)
        handoff, handoff_err = generate_handoff(spec, task_filepath, inbox_dir)
        if handoff_err:
            print(f"error: {handoff_err}", file=sys.stderr)
            return 1
        if len(content.encode("utf-8")) > TASK_BUDGET_BYTES:
            print("error: generated task exceeds hard budget after sequence reservation", file=sys.stderr)
            return 1

    # Write task file (force LF line endings on all platforms)
    try:
        with open(task_filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    except OSError as exc:
        print(f"error: failed to write task file: {exc}", file=sys.stderr)
        return 1

    # Append event (force LF line endings on all platforms)
    events_path = os.path.join(inbox_dir, "events.jsonl")
    event = make_event(
        task_id, agent_name, "ASSIGNED", created_at,
        f"Assigned task {task_id} to {agent_name}.", spec
    )
    try:
        append_event_once(events_path, event)
    except OSError as exc:
        print(f"error: failed to append to events.jsonl: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {task_filepath}")
    print(f"Appended event to {events_path}")
    print()
    print("--- Handoff ---")
    print(handoff)
    print()
    print("NOTE: CAL-1 after delivering the handoff, confirm dispatch with:")
    print(
        f"  python -B scripts/afc-assign.py --confirm-dispatch {task_id}"
        f" --confirm-dispatch-agent {agent_name} --inbox {inbox_dir}"
    )
    print("NOTE: CAL-2 records dispatch and arms the watcher with:")
    print(
        f"  python -B scripts/afc-cal2-arm.py --task-id {task_id}"
        f" --inbox {inbox_dir}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
