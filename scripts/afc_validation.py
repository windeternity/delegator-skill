"""Shared validation functions for report frontmatter.

Used by afc-watch.py (watcher intake validation) and
validate-agent-inbox.py (full-suite validation). Single source
of truth for report schema checks.

Python stdlib only. Python 3.8+. No side effects on import.
"""

import re


# ---------------------------------------------------------------------------
# Enum constants (single source of truth)
# ---------------------------------------------------------------------------

VERDICTS = {'GO', 'PARTIAL', 'RED'}

TRUST_LEVELS = {
    'self_claim', 'referenced', 'reproduced',
    'independent_reviewed', 'blocked_or_suspicious',
}

VALIDATION_TIERS = {
    'no-test-needed', 'targeted-test', 'smoke-test',
    'browser-test', 'full-suite', 'production-replay',
}

VALIDATION_RESULTS = {'pass', 'partial', 'fail', 'not_run'}

COORDINATION_MODES = {
    'delegate_full',
    'moa_review',
    'moa_design',
    'moa_patch',
    'moa_synthesis',
}

GUARDRAIL_KEYS = [
    'role_boundary_followed',
    'coordinator_verdict_given',
    'permission_scope_expanded',
    'secrets_private_data_printed',
    'production_default_behavior_changed',
    'commit_push_done',
    'destructive_command_done',
]


# ---------------------------------------------------------------------------
# Dangerous-phrase pattern
# ---------------------------------------------------------------------------

def _build_dangerous_pattern():
    """Build the dangerous-phrase regex without triggering self-match.

    The pattern literals are split with '+' to prevent the validator's own
    scan from matching the specification text in this module's docstrings.
    """
    _DP = lambda *parts: ''.join(parts)
    return re.compile(
        r'(' + _DP('ignore', ' previous instructions|')
        + _DP('push', ' to master|')
        + _DP('pushed', ' to master|')
        + _DP('pushed', ' to|')
        + _DP('committed', ' to|')
        + _DP('commit', ' to|')
        + _DP('force', ' push|')
        + _DP('destructive', ' command (?:was )?(?:executed|run)|')
        + _DP('(?:executed|ran) destructive', ' command|')
        + _DP('deleted', ' branch|')
        + _DP('secrets', ' were printed|')
        + _DP('printed', ' secrets|')
        + _DP('exposed', ' secret|')
        + _DP('leaked', ' token|')
        + _DP('reveal', ' secrets|')
        + _DP('bypass', ' permission|')
        + _DP('branch', ' w' + 'as deleted|')
        + _DP('w', 'as deleted|')
        + _DP('token', ' w' + 'as leaked|')
        + _DP('w', 'as leaked|')
        + _DP('secrets', ' were leaked)'),
        re.IGNORECASE
    )


_DANGEROUS_PATTERN = _build_dangerous_pattern()


def get_dangerous_pattern():
    """Return the shared compiled dangerous-phrase pattern."""
    return _DANGEROUS_PATTERN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bool_enabled(value):
    """Check if a value is a boolean-ish 'true' / 'yes' / 'approved'."""
    s = str(value).strip().lower()
    return s in ('true', 'yes', 'approved')


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------

def validate_report_schema(data, body=None, task=None):
    """Validate report frontmatter data against the full schema.

    Args:
        data: Parsed frontmatter dict.
        body: Optional report body text (for dangerous-phrase scan).
        task: Optional task frontmatter dict (for cross-checks).

    Returns:
        (is_valid, reasons_list) where reasons_list is empty on success.
    """
    reasons = []

    # --- Required fields ---
    for field in ('task_id', 'agent_name', 'verdict'):
        if not data.get(field):
            reasons.append("missing required field: {}".format(field))

    # --- Verdict enum ---
    verdict = str(data.get('verdict', '')).strip().upper()
    if verdict and verdict not in VERDICTS:
        reasons.append("invalid verdict: {}".format(verdict))

    coordination_mode = str(data.get('coordination_mode', '') or '').strip()
    if coordination_mode and coordination_mode not in COORDINATION_MODES:
        reasons.append(
            "invalid coordination_mode: {} (allowed: {})".format(
                coordination_mode, ', '.join(sorted(COORDINATION_MODES))
            )
        )

    # --- evidence_refs ---
    evidence_refs = data.get('evidence_refs')
    if evidence_refs is None or (isinstance(evidence_refs, list) and len(evidence_refs) == 0):
        reasons.append("evidence_refs must be a non-empty list")

    # --- evidence_trust ---
    et = data.get('evidence_trust')
    if not isinstance(et, dict):
        reasons.append("evidence_trust must be a dictionary")
    else:
        tl = str(et.get('trust_level', '')).strip().lower()
        if tl not in TRUST_LEVELS:
            reasons.append("invalid trust_level: {} (allowed: {})".format(
                tl, ', '.join(sorted(TRUST_LEVELS))))
        if _bool_enabled(et.get('prompt_injection_suspected')):
            reasons.append("prompt_injection_suspected is true")
        if _bool_enabled(et.get('permission_escalation_requested')):
            reasons.append("permission_escalation_requested is true")

    # --- guardrails ---
    gr = data.get('guardrails')
    if not isinstance(gr, dict):
        reasons.append("guardrails must be a dictionary")
    else:
        for key in GUARDRAIL_KEYS:
            if key not in gr:
                reasons.append("missing guardrails.{}".format(key))
        if _bool_enabled(gr.get('commit_push_done')):
            reasons.append("commit_push_done is true")
        if _bool_enabled(gr.get('destructive_command_done')):
            reasons.append("destructive_command_done is true")
        if str(gr.get('role_boundary_followed')).strip().lower() in ('false', 'no'):
            reasons.append("role_boundary_followed is false")
        if _bool_enabled(gr.get('coordinator_verdict_given')):
            reasons.append("coordinator_verdict_given is true")
        if _bool_enabled(gr.get('permission_scope_expanded')):
            reasons.append("permission_scope_expanded is true")
        if _bool_enabled(gr.get('secrets_private_data_printed')):
            reasons.append("secrets_private_data_printed is true")
        if _bool_enabled(gr.get('production_default_behavior_changed')):
            reasons.append("production_default_behavior_changed is true")

    # --- validation ---
    val = data.get('validation')
    if not isinstance(val, dict):
        reasons.append("validation must be a dictionary")
    else:
        vt = str(val.get('tier', '')).strip().lower()
        if vt and vt not in VALIDATION_TIERS:
            reasons.append("invalid validation.tier: {} (allowed: {})".format(
                vt, ', '.join(sorted(VALIDATION_TIERS))))
        vr = str(val.get('result', '')).strip().lower()
        if vr and vr not in VALIDATION_RESULTS:
            reasons.append("invalid validation.result: {} (allowed: {})".format(
                vr, ', '.join(sorted(VALIDATION_RESULTS))))

    # --- Dangerous phrase scan (if body provided) ---
    if body:
        pi_suspected = (
            isinstance(et, dict) and _bool_enabled(et.get('prompt_injection_suspected'))
        )
        for match in _DANGEROUS_PATTERN.findall(body):
            if not pi_suspected:
                reasons.append(
                    "body contains dangerous phrase '{}' but "
                    "prompt_injection_suspected is not true".format(match)
                )

    # --- Cross-checks with task (if task provided) ---
    if task:
        if task.get('agent_name') != data.get('agent_name'):
            reasons.append("agent_name does not match task agent_name")
        for field in ('coordination_mode', 'comparison_group'):
            task_value = str(task.get(field, '') or '').strip()
            report_value = str(data.get(field, '') or '').strip()
            if task_value != report_value:
                reasons.append("{} does not match task {}".format(field, field))
        ps = task.get('permission_scope')
        if isinstance(ps, dict):
            if not _bool_enabled(ps.get('modify_source')):
                cf = data.get('changed_files')
                if cf is not None and not (
                    isinstance(cf, list) and (
                        len(cf) == 0 or
                        all(str(x).strip().lower() in ('', 'none', '[]') for x in cf)
                    )
                ):
                    reasons.append(
                        "changed_files listed but task permission_scope.modify_source is false"
                    )

    return (len(reasons) == 0, reasons)
