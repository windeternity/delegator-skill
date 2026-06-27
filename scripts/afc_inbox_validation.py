#!/usr/bin/env python3
"""Importable AFC inbox validation core."""

import json
import os
import re
import sys
from datetime import datetime

# Import shared validation constants and function from afc_validation.
# This ensures watcher and formal validator use identical schema checks.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from afc_validation import (  # noqa: E402
    VERDICTS,
    TRUST_LEVELS,
    VALIDATION_TIERS,
    VALIDATION_RESULTS,
    COORDINATION_MODES,
    GUARDRAIL_KEYS,
    get_dangerous_pattern,
)
from afc_frontmatter import (  # noqa: E402
    extract_structured_frontmatter as extract_frontmatter,
)

TEMPLATE_MODE = False
LEGACY_EVENTS = False

def is_placeholder(value):
    """Check if a value is a <PLACEHOLDER> marker."""
    if not isinstance(value, str):
        return False
    return bool(re.match(r'^<[A-Z_0-9]+>$', value.strip()))

ALLOWED_SCHEMAS = {
    'agent-file-coordination/task',
    'agent-file-coordination/report',
    'agent-file-coordination/coordinator-verdict',
    'agent-file-coordination/roster',
    'agent-file-coordination/status-board',
    'agent-file-coordination/worktree-locks',
}

ROLE_VALUES = {
    'coordinator',
    'planner',
    'implementer',
    'reviewer',
    'smoke',
    'docs',
    'research',
    'other',
}

PROTOCOL_MODES = {
    'full-skill',
    'worker-brief',
    'task-only',
    'manual-paste',
    'unknown',
}

COORDINATOR_AUTHORITY_VALUES = {'yes', 'no', 'limited'}
TASK_STATUSES = {
    'DRAFT',
    'ASSIGNED',
    'RUNNING',
    'REPORTED',
    'REVIEWING',
    'NEEDS_FIX',
    'CLOSED_GO',
    'CLOSED_PARTIAL',
    'CLOSED_RED',
    'BLOCKED',
    'CANCELLED',
    'SUPERSEDED',
}
WORKSPACE_MODES = {
    'read_only_shared',
    'existing_edit_worktree',
    'dedicated_worktree_required',
    'manual_worktree_needed',
}
# VERDICTS, TRUST_LEVELS, VALIDATION_TIERS, VALIDATION_RESULTS are imported
# from afc_validation as the single source of truth — no local duplicates.

LOCK_STATUSES = {
    'ACTIVE',
    'RELEASED',
    'BLOCKED',
    'STALE',
    'SUPERSEDED',
}
EVENT_TYPES = {
    'ROSTER_UPDATED',
    'TASK_CREATED',
    'TASK_ASSIGNED',
    'TASK_DISPATCHED',
    'TASK_STARTED',
    'REPORT_RECEIVED',
    'REPORT_REJECTED',
    'STATUS_UPDATED',
    'WORKTREE_LOCKED',
    'WORKTREE_RELEASED',
    'COORDINATOR_VERDICT',
    'TASK_CLOSED',
    'TASK_BLOCKED',
    'TASK_SUPERSEDED',
    'REPAIR_ROUND',
}
TASK_EVENT_TYPES = {
    'TASK_CREATED',
    'TASK_ASSIGNED',
    'TASK_DISPATCHED',
    'TASK_STARTED',
    'REPORT_RECEIVED',
    'COORDINATOR_VERDICT',
    'TASK_CLOSED',
    'TASK_BLOCKED',
    'TASK_SUPERSEDED',
    'REPAIR_ROUND',
}
EVENT_PHASES = {
    'assignment',
    'dispatch',
    'execution',
    'report_intake',
    'review',
    'verdict',
    'closure',
    'status',
}
ATTRIBUTION_FIELDS = {
    'trace_id',
    'coordinator_thread_id',
    'coordinator_root_thread_id',
}
SAFE_ATTRIBUTION_RE = re.compile(r'^[A-Za-z0-9._-]+$')

# Legacy event types observed in real long-lived inboxes (append-only compat).
# These are accepted only when --legacy-events is passed.
LEGACY_EVENT_TYPES = {
    'DECISION',
    'NOTE',
    'PR_OPENED',
    'SNAPSHOT_BUILT',
    'SNAPSHOT_READY',
    'TASK_NEEDS_FIX',
}

# Legacy task/status values observed in real long-lived inboxes.
LEGACY_TASK_STATUSES = {
    '-',
    'HELD',
}
SCHEMAS_WITHOUT_TASK_ID = {
    'agent-file-coordination/roster',
    'agent-file-coordination/status-board',
    'agent-file-coordination/worktree-locks',
}

def schema_type(data):
    st1 = data.get('schema')
    st2 = data.get('schema_type')
    return st1 or st2

def normalized(value):
    if isinstance(value, bool):
        return 'yes' if value else 'no'
    s = str(value).strip()
    if TEMPLATE_MODE and is_placeholder(s):
        return s
    return s.lower()

def bool_enabled(value):
    return normalized(value) in {'true', 'yes', 'approved'}

def is_empty_file_list(value):
    if value is None:
        return True
    if isinstance(value, list):
        return len(value) == 0 or all(str(item).strip().lower() in {'', 'none', '[]'} for item in value)
    return str(value).strip().lower() in {'', 'none', '[]'}

def has_section(body, section_name):
    pattern = rf'(?im)^##\s+{re.escape(section_name)}(?:\s*/.*)?\s*$'
    return re.search(pattern, body) is not None

def split_markdown_row(line):
    return [cell.strip() for cell in line.strip().strip('|').split('|')]

def parse_markdown_table(body):
    lines = [line.strip() for line in body.splitlines() if line.strip().startswith('|')]
    if len(lines) < 2:
        return [], []
    headers = split_markdown_row(lines[0])
    rows = []
    for line in lines[2:]:
        cells = split_markdown_row(line)
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return headers, rows

def validate_required_table_headers(headers, required_headers, table_name, errs):
    for header in required_headers:
        if header not in headers:
            errs.append(f"{table_name} missing column '{header}'")

def empty_cell(value):
    s = str(value or '').strip()
    if TEMPLATE_MODE and is_placeholder(s):
        return False
    return s.lower() in {'', 'none', 'n/a', 'unknown'}

def validate_permission_scope(ps, errs):
    if not isinstance(ps, dict):
        errs.append("permission_scope must be a dictionary")
        return False

    for key in ['read_files', 'write_task_files', 'write_reports', 'modify_source', 'run_commands', 'network_access', 'commit_push', 'destructive_actions']:
        if key not in ps:
            errs.append(f"permission_scope missing '{key}'")

    for key in ['read_files', 'write_task_files', 'write_reports', 'modify_source']:
        if key not in ps:
            continue
        value = normalized(ps.get(key, ''))
        if TEMPLATE_MODE and is_placeholder(value):
            continue
        if value not in {'yes', 'no', 'true', 'false'}:
            errs.append(f"Invalid {key}: {value}")

    rc = normalized(ps.get('run_commands', ''))
    if not (TEMPLATE_MODE and is_placeholder(rc)):
        if rc not in ['none', 'read_only', 'tests_only', 'bounded']:
            errs.append(f"Invalid run_commands: {rc}")

    na = normalized(ps.get('network_access', ''))
    if not (TEMPLATE_MODE and is_placeholder(na)):
        if na not in ['none', 'docs_only', 'allowed']:
            errs.append(f"Invalid network_access: {na}")

    cp = normalized(ps.get('commit_push', ''))
    if not (TEMPLATE_MODE and is_placeholder(cp)):
        if cp not in ['no', 'false', 'ask', 'approved']:
            errs.append(f"Invalid commit_push: {cp}")

    if not (TEMPLATE_MODE and is_placeholder(str(ps.get('destructive_actions', '')))):
        if bool_enabled(ps.get('destructive_actions')):
            errs.append("destructive_actions must not be enabled")

    return isinstance(ps, dict)

def validate_workspace(workspace, permission_scope, errs):
    if not isinstance(workspace, dict):
        errs.append("workspace must be a dictionary")
        return

    for key in ['mode', 'path', 'may_create_worktree']:
        if key not in workspace:
            errs.append(f"workspace missing '{key}'")

    mode = normalized(workspace.get('mode', ''))
    if not (TEMPLATE_MODE and is_placeholder(mode)):
        if mode not in WORKSPACE_MODES:
            errs.append(f"Invalid workspace.mode: {mode}")

    may_create = normalized(workspace.get('may_create_worktree', ''))
    if not (TEMPLATE_MODE and is_placeholder(may_create)):
        if may_create not in {'yes', 'no', 'ask'}:
            errs.append(f"Invalid workspace.may_create_worktree: {may_create}")

    if not TEMPLATE_MODE:
        if mode == 'read_only_shared' and isinstance(permission_scope, dict) and bool_enabled(permission_scope.get('modify_source')):
            errs.append("read_only_shared workspace cannot allow modify_source")

        if mode == 'manual_worktree_needed' and may_create == 'yes':
            errs.append("manual_worktree_needed means the assigned worker should not create the worktree")

def validate_task(filepath, data, body, errs):
    for key in ['agent_name', 'role', 'protocol_mode', 'coordinator_authority', 'status', 'permission_scope', 'workspace', 'validation_tier', 'report_path']:
        if key not in data:
            errs.append(f"Missing {key}")

    role = normalized(data.get('role', ''))
    if not (TEMPLATE_MODE and is_placeholder(role)):
        if role not in ROLE_VALUES:
            errs.append(f"Invalid role: {role}")

    protocol_mode = normalized(data.get('protocol_mode', ''))
    if not (TEMPLATE_MODE and is_placeholder(protocol_mode)):
        if protocol_mode not in PROTOCOL_MODES:
            errs.append(f"Invalid protocol_mode: {protocol_mode}")

    coordinator_authority = normalized(data.get('coordinator_authority', ''))
    if not (TEMPLATE_MODE and is_placeholder(coordinator_authority)):
        if coordinator_authority not in COORDINATOR_AUTHORITY_VALUES:
            errs.append(f"Invalid coordinator_authority: {coordinator_authority}")

    status = str(data.get('status', '')).strip()
    if TEMPLATE_MODE and is_placeholder(status):
        pass
    else:
        status_upper = status.upper()
        if status_upper not in TASK_STATUSES:
            errs.append(f"Invalid status: {status_upper}")

    if not TEMPLATE_MODE:
        if role != 'coordinator' and coordinator_authority == 'yes':
            errs.append("Only coordinator tasks may declare coordinator_authority: yes")
        if protocol_mode != 'full-skill' and coordinator_authority == 'yes':
            errs.append("Only full-skill protocol mode may declare coordinator_authority: yes")
        if role != 'coordinator' and not has_section(body, 'Role Boundary'):
            errs.append("Worker task is missing ## Role Boundary")

    coordination_mode = str(data.get('coordination_mode', '') or '').strip()
    if not (TEMPLATE_MODE and is_placeholder(coordination_mode)):
        if coordination_mode and coordination_mode not in COORDINATION_MODES:
            errs.append(
                "Invalid coordination_mode: {} (allowed: {})".format(
                    coordination_mode, ', '.join(sorted(COORDINATION_MODES))
                )
            )

    ps = data.get('permission_scope')
    validate_permission_scope(ps, errs)
    validate_workspace(data.get('workspace'), ps, errs)

    # Release-Operator gate: commit_push: approved requires ## Release Operations Scope in body
    if not TEMPLATE_MODE and isinstance(ps, dict):
        cp = normalized(ps.get('commit_push', ''))
        if cp == 'approved' and not has_section(body, 'Release Operations Scope'):
            errs.append("commit_push is approved but body is missing ## Release Operations Scope section")

    vt = normalized(data.get('validation_tier', ''))
    if not (TEMPLATE_MODE and is_placeholder(vt)):
        if vt not in VALIDATION_TIERS:
            errs.append(f"Invalid validation_tier: {vt}")

    for field in ATTRIBUTION_FIELDS:
        value = str(data.get(field, '') or '').strip()
        if value and not SAFE_ATTRIBUTION_RE.match(value):
            errs.append(f"Invalid {field}: {value}")

MOA_SYNTHESIS_REQUIRED_SECTIONS = [
    'Summary',
    'Agreements',
    'Contradictions',
    'Evidence Quality',
    'Validation Gaps',
    'Unsafe Or Out-Of-Scope Recommendations',
    'Recommendation',
    'Remaining Uncertainty',
]

def validate_report(filepath, data, body, tasks, errs):
    verdict = str(data.get('verdict', '')).strip()
    if TEMPLATE_MODE and is_placeholder(verdict):
        pass
    else:
        verdict_upper = verdict.upper()
        if verdict_upper not in VERDICTS:
            errs.append(f"Invalid verdict: {verdict_upper}")

    if not data.get('agent_name'):
        errs.append("Missing agent_name")

    coordination_mode = str(data.get('coordination_mode', '') or '').strip()
    if not (TEMPLATE_MODE and is_placeholder(coordination_mode)):
        if coordination_mode and coordination_mode not in COORDINATION_MODES:
            errs.append(
                "Invalid coordination_mode: {} (allowed: {})".format(
                    coordination_mode, ', '.join(sorted(COORDINATION_MODES))
                )
            )

    # MOA synthesis report section validation
    if coordination_mode == 'moa_synthesis':
        for section in MOA_SYNTHESIS_REQUIRED_SECTIONS:
            if not has_section(body, section):
                errs.append(f"MOA synthesis report missing required section: ## {section}")

    evidence_refs = data.get('evidence_refs')
    if is_empty_file_list(evidence_refs):
        errs.append("evidence_refs must be a non-empty list")

    validation = data.get('validation')
    if not isinstance(validation, dict):
        errs.append("validation must be a dictionary")
    else:
        vt = normalized(validation.get('tier', ''))
        if not (TEMPLATE_MODE and is_placeholder(vt)):
            if vt not in VALIDATION_TIERS:
                errs.append(f"Invalid validation.tier: {vt} (allowed: {', '.join(sorted(VALIDATION_TIERS))})")

        result = normalized(validation.get('result', ''))
        if not (TEMPLATE_MODE and is_placeholder(result)):
            if result not in VALIDATION_RESULTS:
                errs.append(f"Invalid validation.result: {result} (allowed: {', '.join(sorted(VALIDATION_RESULTS))})")

    et = data.get('evidence_trust')
    pi_suspected = False
    if not isinstance(et, dict):
        errs.append("evidence_trust must be a dictionary")
    else:
        tl = normalized(et.get('trust_level', ''))
        if not (TEMPLATE_MODE and is_placeholder(tl)):
            if tl not in TRUST_LEVELS:
                errs.append(f"Invalid trust_level: {tl} (allowed: {', '.join(sorted(TRUST_LEVELS))})")

        # Use bool_enabled (true/yes/approved) for guardrail booleans so a
        # frontmatter value like `commit_push_done: yes` is caught the same way
        # validate_report_schema (afc_validation) does. Without this, the inbox
        # validator could accept a report the watcher rejects, or vice versa.
        pi_suspected = bool_enabled(et.get('prompt_injection_suspected', ''))
        if pi_suspected:
            errs.append("prompt_injection_suspected is true!")
        if bool_enabled(et.get('permission_escalation_requested', '')):
            errs.append("permission_escalation_requested is true!")

    report_guardrails = data.get('guardrails', {})
    if not isinstance(report_guardrails, dict):
        errs.append("guardrails must be a dictionary")
    else:
        for key in GUARDRAIL_KEYS:
            if key not in report_guardrails:
                errs.append(f"guardrails missing '{key}'")

        if bool_enabled(report_guardrails.get('commit_push_done', '')):
            # Allow for Release-Operator tasks whose permission_scope.commit_push
            # is approved. Reject for all other workers (default-deny).
            task = tasks.get(data.get('task_id'))
            task_commit_approved = (
                isinstance(task, dict)
                and isinstance(task.get('permission_scope'), dict)
                and normalized(task['permission_scope'].get('commit_push', '')) == 'approved'
            )
            if not task_commit_approved:
                errs.append("Report claims commit_push_done")
        if bool_enabled(report_guardrails.get('destructive_command_done', '')):
            errs.append("Report claims destructive_command_done")
        if bool_enabled(report_guardrails.get('secrets_private_data_printed', '')):
            errs.append("Report claims secrets_private_data_printed")
        if bool_enabled(report_guardrails.get('production_default_behavior_changed', '')):
            errs.append("Report claims production_default_behavior_changed")
        if str(report_guardrails.get('role_boundary_followed', '')).strip().lower() in ('false', 'no'):
            errs.append("Report claims role_boundary_followed is false")
        if bool_enabled(report_guardrails.get('coordinator_verdict_given', '')):
            errs.append("Worker report claims coordinator_verdict_given")
        if bool_enabled(report_guardrails.get('permission_scope_expanded', '')):
            errs.append("Worker report claims permission_scope_expanded")

    if not TEMPLATE_MODE:
        task = tasks.get(data.get('task_id'))
        if task:
            if task.get('agent_name') != data.get('agent_name'):
                errs.append("Report agent_name does not match task agent_name")
            for field in ('coordination_mode', 'comparison_group'):
                task_value = str(task.get(field, '') or '').strip()
                report_value = str(data.get(field, '') or '').strip()
                if task_value != report_value:
                    errs.append(
                        "Report {} does not match task {}".format(field, field)
                    )

            ps = task.get('permission_scope')
            if isinstance(ps, dict) and not bool_enabled(ps.get('write_reports')):
                errs.append("Report exists but task permission_scope.write_reports is not enabled")
            if isinstance(ps, dict) and not bool_enabled(ps.get('modify_source')) and not is_empty_file_list(data.get('changed_files')):
                errs.append("Report lists changed_files but task permission_scope.modify_source is false")

    matches = get_dangerous_pattern().findall(body)
    for match in matches:
        if not pi_suspected:
            errs.append(f"Body contains dangerous phrase '{match}' but prompt_injection_suspected is not true")

def validate_coordinator_verdict(data, errs):
    for req in ['verdict', 'score', 'score_breakdown', 'evidence_checked', 'blockers', 'follow_up']:
        if req not in data:
            errs.append(f"Missing {req} in coordinator-verdict")

    verdict = str(data.get('verdict', '')).strip()
    if TEMPLATE_MODE and is_placeholder(verdict):
        pass
    else:
        verdict_upper = verdict.upper()
        if verdict_upper not in VERDICTS:
            errs.append(f"Invalid verdict: {verdict_upper}")

    score_raw = data.get('score')
    if TEMPLATE_MODE and is_placeholder(str(score_raw)):
        pass
    else:
        try:
            score = int(score_raw)
            if score < 0 or score > 14:
                errs.append(f"score must be 0-14, got {score}")
        except Exception:
            errs.append("score must be an integer")

def validate_roster(body, errs):
    headers, rows = parse_markdown_table(body)
    required_headers = ['Agent Name', 'Role', 'Tool', 'Model', 'Protocol Mode', 'Coordinator Authority', 'Worktree Capability']
    for header in required_headers:
        if header not in headers:
            errs.append(f"Roster missing column '{header}'")

    if not rows:
        errs.append("Roster has no agent rows")
        return

    coordinator_yes_count = 0
    for row in rows:
        role = normalized(row.get('Role', ''))
        protocol_mode = normalized(row.get('Protocol Mode', ''))
        coordinator_authority = normalized(row.get('Coordinator Authority', ''))

        if not (TEMPLATE_MODE and is_placeholder(role)):
            if role not in ROLE_VALUES:
                errs.append(f"Roster row '{row.get('Agent Name', '<unknown>')}' has invalid Role: {role}")
        if not (TEMPLATE_MODE and is_placeholder(protocol_mode)):
            if protocol_mode not in PROTOCOL_MODES:
                errs.append(f"Roster row '{row.get('Agent Name', '<unknown>')}' has invalid Protocol Mode: {protocol_mode}")
        if not (TEMPLATE_MODE and is_placeholder(coordinator_authority)):
            if coordinator_authority not in COORDINATOR_AUTHORITY_VALUES:
                errs.append(f"Roster row '{row.get('Agent Name', '<unknown>')}' has invalid Coordinator Authority: {coordinator_authority}")

        if coordinator_authority == 'yes':
            coordinator_yes_count += 1
            if not TEMPLATE_MODE:
                if role != 'coordinator':
                    errs.append(f"Roster row '{row.get('Agent Name', '<unknown>')}' has coordinator authority but Role is not coordinator")
                if protocol_mode != 'full-skill':
                    errs.append(f"Roster row '{row.get('Agent Name', '<unknown>')}' has coordinator authority but Protocol Mode is not full-skill")

    if not TEMPLATE_MODE:
        if coordinator_yes_count == 0:
            errs.append("Roster must declare exactly one coordinator with Coordinator Authority: yes")
        if coordinator_yes_count > 1:
            errs.append("Roster must not declare more than one coordinator with Coordinator Authority: yes")

def validate_status_board(data, body, errs):
    if not TEMPLATE_MODE and not data.get('updated_at'):
        errs.append("Missing updated_at in status-board")

    headers, rows = parse_markdown_table(body)
    required_headers = ['task_id', 'assigned_agent', 'role', 'protocol_mode', 'status', 'workspace', 'report_path', 'next_action']
    validate_required_table_headers(headers, required_headers, "Status board", errs)

    if not rows:
        # Zero-row status board is valid (long-lived inbox with no active tasks)
        return

    for row in rows:
        task_id = row.get('task_id', '<unknown>')
        for header in required_headers:
            if empty_cell(row.get(header)):
                errs.append(f"Status board row '{task_id}' has empty {header}")

        role = normalized(row.get('role', ''))
        if not (TEMPLATE_MODE and is_placeholder(role)):
            if role not in ROLE_VALUES:
                errs.append(f"Status board row '{task_id}' has invalid role: {role}")

        protocol_mode = normalized(row.get('protocol_mode', ''))
        if not (TEMPLATE_MODE and is_placeholder(protocol_mode)):
            if protocol_mode not in PROTOCOL_MODES:
                errs.append(f"Status board row '{task_id}' has invalid protocol_mode: {protocol_mode}")

        status = str(row.get('status', '')).strip()
        if TEMPLATE_MODE and is_placeholder(status):
            pass
        else:
            status_upper = status.upper()
            if status_upper not in TASK_STATUSES:
                errs.append(f"Status board row '{task_id}' has invalid status: {status_upper}")

def validate_worktree_locks(data, body, errs):
    if not TEMPLATE_MODE and not data.get('updated_at'):
        errs.append("Missing updated_at in worktree-locks")

    headers, rows = parse_markdown_table(body)
    required_headers = ['lock_id', 'task_id', 'owner_agent', 'workspace_mode', 'worktree_path', 'branch', 'locked_files_or_areas', 'status']
    validate_required_table_headers(headers, required_headers, "Worktree locks", errs)

    if not rows:
        if not TEMPLATE_MODE:
            errs.append("Worktree locks has no lock rows")
        return

    for row in rows:
        lock_id = row.get('lock_id', '<unknown>')
        for header in required_headers:
            if empty_cell(row.get(header)):
                errs.append(f"Worktree lock row '{lock_id}' has empty {header}")

        workspace_mode = normalized(row.get('workspace_mode', ''))
        if not (TEMPLATE_MODE and is_placeholder(workspace_mode)):
            if workspace_mode not in WORKSPACE_MODES:
                errs.append(f"Worktree lock row '{lock_id}' has invalid workspace_mode: {workspace_mode}")

        status = str(row.get('status', '')).strip()
        if TEMPLATE_MODE and is_placeholder(status):
            pass
        else:
            status_upper = status.upper()
            if status_upper not in LOCK_STATUSES:
                errs.append(f"Worktree lock row '{lock_id}' has invalid status: {status_upper}")

def validate_event_record(record, line_num, errs):
    if not isinstance(record, dict):
        errs.append(f"Line {line_num}: event must be a JSON object")
        return

    if record.get('schema') != 'agent-file-coordination/event':
        errs.append(f"Line {line_num}: event schema must be agent-file-coordination/event")

    for key in ['schema_version', 'event_id', 'event_type', 'created_at', 'summary']:
        if empty_cell(record.get(key)):
            errs.append(f"Line {line_num}: missing {key}")

    event_type = str(record.get('event_type', '')).strip().upper()
    valid_types = EVENT_TYPES | (LEGACY_EVENT_TYPES if LEGACY_EVENTS else set())
    if event_type not in valid_types:
        errs.append(f"Line {line_num}: invalid event_type: {event_type}")

    if event_type in TASK_EVENT_TYPES and empty_cell(record.get('task_id')):
        errs.append(f"Line {line_num}: task_id is required for {event_type}")

    occurred_at = str(record.get('occurred_at', '') or '').strip()
    if occurred_at:
        try:
            parsed = datetime.fromisoformat(occurred_at.replace('Z', '+00:00'))
            if 'T' not in occurred_at or parsed.tzinfo is None:
                raise ValueError
        except ValueError:
            errs.append(
                f"Line {line_num}: occurred_at must be an ISO 8601 datetime with timezone"
            )

    phase = str(record.get('phase', '') or '').strip()
    if phase and phase not in EVENT_PHASES:
        errs.append(f"Line {line_num}: invalid phase: {phase}")

    for field in ATTRIBUTION_FIELDS:
        value = str(record.get(field, '') or '').strip()
        if value and not SAFE_ATTRIBUTION_RE.match(value):
            errs.append(f"Line {line_num}: invalid {field}: {value}")

    status = record.get('status')
    if status is not None:
        status_upper = str(status).strip().upper()
        valid_statuses = TASK_STATUSES | (LEGACY_TASK_STATUSES if LEGACY_EVENTS else set())
        if status_upper not in valid_statuses:
            errs.append(f"Line {line_num}: invalid status: {status}")

    lock_status = record.get('lock_status')
    if lock_status is not None and str(lock_status).strip().upper() not in LOCK_STATUSES:
        errs.append(f"Line {line_num}: invalid lock_status: {lock_status}")

def validate_event_log(filepath):
    errs = []
    event_count = 0

    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            for line_num, line in enumerate(f, 1):
                stripped = line.strip()
                if not stripped:
                    continue
                event_count += 1
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    errs.append(f"Line {line_num}: invalid JSON: {exc.msg}")
                    continue
                validate_event_record(record, line_num, errs)
    except Exception as exc:
        errs.append(f"Could not read event log: {exc}")

    if event_count == 0:
        errs.append("Event log has no events")

    return errs

def run_cross_check(target_dir, parsed_files, task_ids_on_disk):
    """Run cross-file consistency checks. Returns list of error strings."""
    errs = []

    # Collect report task_ids and check they match a task file on disk
    for filepath, (data, body, _) in parsed_files.items():
        st = schema_type(data)
        if st == 'agent-file-coordination/report':
            tid = data.get('task_id')
            if tid and tid not in task_ids_on_disk:
                errs.append(f"CROSS-CHECK: report {os.path.basename(filepath)} references task_id '{tid}' but no matching task file found")

    # Parse STATUS.md task_ids
    status_task_ids = set()
    status_file = None
    for filepath, (data, body, _) in parsed_files.items():
        st = schema_type(data)
        if st == 'agent-file-coordination/status-board':
            status_file = filepath
            _, rows = parse_markdown_table(body)
            for row in rows:
                tid = row.get('task_id', '').strip()
                if tid and not (TEMPLATE_MODE and is_placeholder(tid)):
                    status_task_ids.add(tid)

    # Check STATUS.md task_ids match task files on disk
    for tid in status_task_ids:
        if tid not in task_ids_on_disk:
            errs.append(f"CROSS-CHECK: STATUS.md references task_id '{tid}' but no matching task file found")

    # Parse WORKTREE_LOCKS.md task_ids and check against STATUS.md
    if status_file is not None:
        for filepath, (data, body, _) in parsed_files.items():
            st = schema_type(data)
            if st == 'agent-file-coordination/worktree-locks':
                _, rows = parse_markdown_table(body)
                for row in rows:
                    tid = row.get('task_id', '').strip()
                    if tid and not (TEMPLATE_MODE and is_placeholder(tid)):
                        if tid not in status_task_ids:
                            errs.append(f"CROSS-CHECK: WORKTREE_LOCKS.md row references task_id '{tid}' but not found in STATUS.md")

    return errs


def _is_excluded_by_active_only(filepath, target):
    """Check if filepath should be excluded in --active-only mode.

    Excludes files under archive/ and artifacts/ subdirectories.
    """
    try:
        rel = os.path.relpath(filepath, target)
    except ValueError:
        return False
    parts = rel.replace("\\", "/").split("/")
    # Exclude if any parent directory (not the file itself) is archive or artifacts
    return any(p in ("archive", "artifacts") for p in parts[:-1])


def validate_paths(paths, cross_check=False, target_dir=None,
                   template_mode=False, legacy_events=False):
    """Validate an explicit set of Markdown/JSONL paths.

    Returns structured file and cross-check results without printing or
    exiting. This is the reusable entrypoint for intake and the CLI wrapper.
    """
    global TEMPLATE_MODE, LEGACY_EVENTS
    TEMPLATE_MODE = bool(template_mode)
    LEGACY_EVENTS = bool(legacy_events)

    md_files = [path for path in paths if path.endswith('.md')]
    jsonl_files = [path for path in paths if path.endswith('.jsonl')]
    tasks = {}
    parsed_files = {}

    for filepath in md_files:
        data, body, fm_errs = extract_frontmatter(filepath)
        if data is not None or fm_errs:
            if data is None:
                data = {}
            parsed_files[filepath] = (data, body, list(fm_errs))
            if schema_type(data) == 'agent-file-coordination/task':
                task_id = data.get('task_id')
                if task_id:
                    tasks[task_id] = data

    file_results = []
    for filepath, (data, body, fm_errs) in parsed_files.items():
        errs = list(fm_errs)
        warnings = []
        st1 = data.get('schema')
        st2 = data.get('schema_type')

        if st1 and st2 and st1 != st2:
            errs.append("schema and schema_type have different values")

        st = schema_type(data)
        if not st:
            if (
                'task_id' in data
                or 'verdict' in data
                or 'permission_scope' in data
            ):
                errs.append(
                    "Missing schema/schema_type but file contains "
                    "coordination fields"
                )
            typo_keys = [
                key for key in data.keys()
                if 'schem' in key.lower()
                and key not in ['schema', 'schema_type', 'schema_version']
            ]
            if typo_keys:
                errs.append("Suspected schema typo: {}".format(typo_keys))
            if errs:
                file_results.append({
                    "path": filepath,
                    "schema": "",
                    "errors": errs,
                    "warnings": warnings,
                })
            continue

        if st not in ALLOWED_SCHEMAS:
            errs.append("Unknown schema: {}".format(st))
        if not data.get('schema_version'):
            errs.append("Missing schema_version")
        if (
            st not in SCHEMAS_WITHOUT_TASK_ID
            and not data.get('task_id')
            and not (
                TEMPLATE_MODE
                and st == 'agent-file-coordination/task'
            )
        ):
            errs.append("Missing task_id")

        if st == 'agent-file-coordination/task':
            validate_task(filepath, data, body, errs)
        elif st == 'agent-file-coordination/report':
            validate_report(filepath, data, body, tasks, errs)
        elif st == 'agent-file-coordination/coordinator-verdict':
            validate_coordinator_verdict(data, errs)
        elif st == 'agent-file-coordination/roster':
            validate_roster(body, errs)
        elif st == 'agent-file-coordination/status-board':
            validate_status_board(data, body, errs)
        elif st == 'agent-file-coordination/worktree-locks':
            validate_worktree_locks(data, body, errs)

        file_results.append({
            "path": filepath,
            "schema": st,
            "errors": errs,
            "warnings": warnings,
        })

    for filepath in jsonl_files:
        file_results.append({
            "path": filepath,
            "schema": "agent-file-coordination/event-log",
            "errors": validate_event_log(filepath),
            "warnings": [],
        })

    cross_errors = []
    cross_target = target_dir or ""
    if cross_check:
        task_ids_on_disk = set()
        for data, _, _ in parsed_files.values():
            if schema_type(data) == 'agent-file-coordination/task':
                task_id = data.get('task_id')
                if task_id:
                    task_ids_on_disk.add(task_id)
        cross_errors = run_cross_check(
            cross_target, parsed_files, task_ids_on_disk
        )

    has_fail = any(item["errors"] for item in file_results)
    has_fail = has_fail or bool(cross_errors)
    return {
        "ok": not has_fail,
        "files": file_results,
        "cross_check": bool(cross_check),
        "cross_check_target": cross_target,
        "cross_check_errors": cross_errors,
    }


def format_validation_result(result):
    """Render a structured validation result using the CLI text contract."""
    lines = []
    for item in result["files"]:
        if item["errors"]:
            lines.append("FAIL: {}".format(item["path"]))
            lines.extend("  - {}".format(error) for error in item["errors"])
        elif item["warnings"]:
            lines.append("WARN: {}".format(item["path"]))
            lines.extend(
                "  - {}".format(warning) for warning in item["warnings"]
            )
        else:
            lines.append("PASS: {}".format(item["path"]))

    if result["cross_check"]:
        target = result["cross_check_target"]
        if result["cross_check_errors"]:
            lines.append("FAIL: {} (cross-check)".format(target))
            lines.extend(
                "  - {}".format(error)
                for error in result["cross_check_errors"]
            )
        else:
            lines.append("PASS: {} (cross-check)".format(target))
    return lines


def validate_target(target, template_mode=False, cross_check=False,
                    active_only=False, legacy_events=False):
    """Collect and validate one file or directory target."""
    paths = []
    if os.path.isfile(target):
        paths.append(target)
    elif os.path.isdir(target):
        for root, _, files in os.walk(target):
            for filename in files:
                if filename.endswith(('.md', '.jsonl')):
                    paths.append(os.path.join(root, filename))
    else:
        raise ValueError("path not found: {}".format(target))

    if active_only and os.path.isdir(target):
        paths = [
            path for path in paths
            if not _is_excluded_by_active_only(path, target)
        ]

    return validate_paths(
        paths,
        cross_check=cross_check and os.path.isdir(target),
        target_dir=target,
        template_mode=template_mode,
        legacy_events=legacy_events,
    )


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    args = [arg for arg in argv if not arg.startswith('--')]
    flags = [arg for arg in argv if arg.startswith('--')]
    if len(args) < 1:
        print(
            "Usage: python validate-agent-inbox.py [--template-mode] "
            "[--cross-check] [--active-only] [--legacy-events] "
            "<dir-or-file>"
        )
        return 1

    target = args[0]
    try:
        result = validate_target(
            target,
            template_mode='--template-mode' in flags,
            cross_check='--cross-check' in flags,
            active_only='--active-only' in flags,
            legacy_events='--legacy-events' in flags,
        )
    except ValueError as exc:
        print("Error: {}".format(exc))
        return 1

    for line in format_validation_result(result):
        print(line)
    return 0 if result["ok"] else 1


if __name__ == '__main__':
    sys.exit(main())
