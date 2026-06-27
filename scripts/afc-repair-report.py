#!/usr/bin/env python3
"""Surgically repair a rejected worker report's frontmatter.

Closes the CAL-2 schema-reject gap: when a worker writes an invalid report
and its process has already exited, the watcher emits ``report_rejected``
(exit 3) and nothing re-dispatches the task. The coordinator's only recovery
paths today are manual frontmatter editing or a wholesale
``afc-report.py --replace`` regeneration. This tool offers a third, cheaper
option: diagnose the rejection and, for the unambiguous schema mistakes that
recur in practice, apply a one-line frontmatter fix the coordinator approves.

Design stance (respects the protocol author's "schema is a red line"):
  - DEFAULT is dry-run: print exactly what would change, change nothing.
    Only ``--write`` persists the fix.
  - Only FRONMATTER is ever edited. The report body (evidence, verdict
    rationale) is never touched, so the worker's substantive claims are
    preserved.
  - Only UNAMBIGUOUS fixes are applied automatically (enum normalization to
    a single legal value, missing guardrail fields filled with safe defaults).
    Anything semantic (empty evidence_refs, over-budget, dangerous phrase,
    cross-file mismatches) is reported with a precise manual-edit hint and
    left alone.
  - Rejections that are dangerous-phrase or over-budget never write, even
    with ``--write``: those are not frontmatter spelling mistakes.

Usage:
    python afc-repair-report.py <report.md>            # dry-run (default)
    python afc-repair-report.py <report.md> --write    # apply the fix
    python afc-repair-report.py <report.md> --json     # machine-readable
    python afc-repair-report.py <report.md> --task <task.md>  # cross-check

Exit codes:
    0  dry-run diagnostics printed (report valid, or fixable/needs-manual)
    2  --write refused: report has unfixable issues (dangerous phrase / budget);
       or --write was requested but file could not be written safely
"""

import argparse
import json
import os
import re
import sys

from afc_frontmatter import extract_structured_frontmatter
from afc_validation import validate_report_schema


# ---------------------------------------------------------------------------
# Unambiguous enum normalization
# ---------------------------------------------------------------------------
#
# These maps target ONLY the recurring real-world mistakes logged in
# LEARNINGS.md (e.g. trust_level: observed/self_reported/verified, verdict:
# CLOSED_GO, validation.result: passed). Each maps to exactly one legal value,
# so the repair is never a guess. Values not listed here fall through to a
# manual hint and are never auto-fixed.

TRUST_LEVEL_NORM = {
    "verified": "referenced",
    "self_reported": "self_claim",
    "self-reported": "self_claim",
    "selfreported": "self_claim",
    "observed": "referenced",
    "confirmed": "independent_reviewed",
    "high": "referenced",
    "low": "blocked_or_suspicious",
}

# verdict normalization is deliberately NARROW: only values that are
# unambiguously the protocol status (a closed-status variant or the bare
# verdict word), or a clear casing of it. We do NOT auto-map subjective words
# like "ok"/"green"/"pass"/"blocked"/"stop" to a verdict, because choosing
# GO vs PARTIAL vs RED for those is a coordinator judgment, not a spelling fix
# — and the worker's body may justify a different verdict. Those fall through
# to a manual hint so the coordinator reads the report and decides.
VERDICT_NORM = {
    "closed_go": "GO",
    "closedgo": "GO",
    "go": "GO",
    "closed_partial": "PARTIAL",
    "closedpartial": "PARTIAL",
    "partial": "PARTIAL",
    "closed_red": "RED",
    "closedred": "RED",
    "red": "RED",
}

VALIDATION_RESULT_NORM = {
    "passed": "pass",
    "passing": "pass",
    "ok": "pass",
    "success": "pass",
    "succeeded": "pass",
    "good": "pass",
    "partial": "partial",
    "partially": "partial",
    "failed": "fail",
    "failing": "fail",
    "failure": "fail",
    "error": "fail",
    "skipped": "not_run",
    "not-run": "not_run",
    "notrun": "not_run",
    "n/a": "not_run",
    "none": "not_run",
}

VALIDATION_TIER_NORM = {
    "no_test_needed": "no-test-needed",
    "notestneeded": "no-test-needed",
    "none": "no-test-needed",
    "targeted_test": "targeted-test",
    "targetedtest": "targeted-test",
    "targeted": "targeted-test",
    "smoke_test": "smoke-test",
    "smoketest": "smoke-test",
    "smoke": "smoke-test",
    "browser_test": "browser-test",
    "browsertest": "browser-test",
    "browser": "browser-test",
    "full_suite": "full-suite",
    "fullsuite": "full-suite",
    "full": "full-suite",
    "all": "full-suite",
    "production_replay": "production-replay",
    "productionreplay": "production-replay",
    "replay": "production-replay",
}

# Safe default values for missing guardrail fields, matching
# templates/TEMPLATE_REPORT.md. All default to the safe (deny / no-concern)
# side, so filling a missing field never fabricates an unsafe claim.
#
# Scope note: only guardrails.* keys appear here. validate_report_schema does
# NOT emit per-key "missing evidence_trust.*" reasons (it checks the whole
# evidence_trust map shape and the trust_level value), so there is nothing to
# backfill there — and _classify_missing_reason only matches
# "missing guardrails.<key>". If that ever changes, add the new (parent, child)
# default here and extend the classifier.
MISSING_FIELD_DEFAULTS = {
    ("guardrails", "role_boundary_followed"): "yes",
    ("guardrails", "coordinator_verdict_given"): "no",
    ("guardrails", "permission_scope_expanded"): "no",
    ("guardrails", "secrets_private_data_printed"): "no",
    ("guardrails", "production_default_behavior_changed"): "no",
    ("guardrails", "commit_push_done"): "no",
    ("guardrails", "destructive_command_done"): "no",
}

# Hard refusal categories: even --write will not touch these because they are
# not frontmatter spelling mistakes.
UNFIXABLE_HINTS = {
    "dangerous phrase": "a dangerous phrase in the body is a safety signal, not a typo; review the report manually",
    "evidence_refs must be a non-empty list": "add real evidence paths/commands under evidence_refs in the frontmatter",
    "evidence_trust must be a dictionary": "restructure evidence_trust as a nested mapping with the required keys",
    "validation must be a dictionary": "restructure validation as a nested mapping with tier/result keys",
    "guardrails must be a dictionary": "restructure guardrails as a nested mapping with the required keys",
}


def _read_text(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            content = handle.read()
    except OSError as exc:
        return None, "could not read {}: {}".format(path, exc)
    return content, None


def _split_frontmatter(content):
    """Return (fm_lines, body_text, start_idx, end_idx) or None if no FM block.

    start_idx is the index of the opening '---'; end_idx the closing '---'.
    fm_lines excludes both markers. body_text is everything after the closing
    marker (joined with newlines).
    """
    lines = content.splitlines()
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines) or lines[start].strip() != "---":
        return None
    end = None
    for index in range(start + 1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return None
    fm_lines = lines[start + 1:end]
    body = "\n".join(lines[end + 1:])
    return (fm_lines, body, start, end)


# Regex helpers to locate the exact frontmatter line for a nested field.
# Matches lines like "  trust_level: verified" under an evidence_trust: block.
def _compile_field_locator(parent, child):
    # Match the child key under the parent section. We rely on indentation:
    # parent sits at column 0, child at 2+ spaces.
    return re.compile(
        r"^(\s*)" + re.escape(child) + r":\s*(.*)$"
    )


def _find_parent_block(fm_lines, parent):
    """Return the index of the 'parent:' header line, or None."""
    for index, line in enumerate(fm_lines):
        if line.strip() == parent + ":":
            return index
    return None


def _find_child_line(fm_lines, parent_idx, child):
    """Return index of the child line directly under parent_idx, or None."""
    parent_indent = len(fm_lines[parent_idx]) - len(fm_lines[parent_idx].lstrip())
    for index in range(parent_idx + 1, len(fm_lines)):
        line = fm_lines[index]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= parent_indent:
            break  # left the parent block
        stripped = line.strip()
        if stripped.startswith("- "):
            continue
        key = stripped.split(":", 1)[0].strip() if ":" in stripped else ""
        if key == child:
            return index
    return None


def _current_value(fm_lines, parent, child):
    """Return the raw scalar value string for parent.child, or None if absent."""
    parent_idx = _find_parent_block(fm_lines, parent)
    if parent_idx is None:
        return None
    child_idx = _find_child_line(fm_lines, parent_idx, child)
    if child_idx is None:
        return None
    stripped = fm_lines[child_idx].strip()
    if ":" not in stripped:
        return None
    value = stripped.split(":", 1)[1].strip()
    if value.startswith(("-", "[")):
        return None  # list value, not a scalar
    # strip surrounding quotes
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


# ---------------------------------------------------------------------------
# Diagnosis -> repair plan
# ---------------------------------------------------------------------------

def _classify_enum_reason(reason):
    """Return ('trust_level'|'verdict'|'validation.result'|'validation.tier', value) or None."""
    m = re.match(r"invalid trust_level:\s*(\S+)", reason)
    if m:
        return ("trust_level", m.group(1).rstrip(","))
    m = re.match(r"invalid verdict:\s*(\S+)", reason)
    if m:
        return ("verdict", m.group(1).rstrip(","))
    m = re.match(r"invalid validation\.result:\s*(\S+)", reason)
    if m:
        return ("validation.result", m.group(1).rstrip(","))
    m = re.match(r"invalid validation\.tier:\s*(\S+)", reason)
    if m:
        return ("validation.tier", m.group(1).rstrip(","))
    return None


def _classify_missing_reason(reason):
    """Return ('guardrails', key) or None for a missing-field reason."""
    m = re.match(r"missing guardrails\.(\S+)", reason)
    if m:
        return ("guardrails", m.group(1).rstrip(","))
    return None


def build_plan(reasons, fm_lines):
    """Turn rejection reasons into a list of repair actions.

    Each action is a dict:
      kind: 'enum' | 'add-field'
      field: 'trust_level' | 'verdict' | 'validation.result' |
             'validation.tier' | 'guardrails.<key>' | 'evidence_trust.<key>'
      old: current value (enum) / None (add-field)
      new: the value to write
      unambiguous: bool
    """
    actions = []
    manual = []  # reasons we will not auto-fix

    for reason in reasons:
        handled = False

        enum = _classify_enum_reason(reason)
        if enum:
            field, value = enum
            table = {
                "trust_level": TRUST_LEVEL_NORM,
                "verdict": VERDICT_NORM,
                "validation.result": VALIDATION_RESULT_NORM,
                "validation.tier": VALIDATION_TIER_NORM,
            }[field]
            key = value.lower()
            if key in table:
                actions.append({
                    "kind": "enum",
                    "field": field,
                    "old": value,
                    "new": table[key],
                    "unambiguous": True,
                })
                handled = True
            else:
                manual.append(reason)
                handled = True

        if not handled:
            missing = _classify_missing_reason(reason)
            if missing:
                parent, child = missing
                key = (parent, child)
                if key in MISSING_FIELD_DEFAULTS:
                    actions.append({
                        "kind": "add-field",
                        "field": "{}.{}".format(parent, child),
                        "old": None,
                        "new": MISSING_FIELD_DEFAULTS[key],
                        "unambiguous": True,
                    })
                    handled = True

        if not handled:
            manual.append(reason)

    return actions, manual


# ---------------------------------------------------------------------------
# Apply the plan to frontmatter lines (no body change)
# ---------------------------------------------------------------------------

def apply_actions(fm_lines, actions):
    """Return a new list of frontmatter lines with actions applied."""
    new_lines = list(fm_lines)
    # Apply enum fixes first (modify existing lines), then add-field.
    for action in actions:
        if action["kind"] == "enum":
            _apply_enum(new_lines, action)
    for action in actions:
        if action["kind"] == "add-field":
            _apply_add_field(new_lines, action)
    return new_lines


def _apply_enum(fm_lines, action):
    field = action["field"]
    new_value = action["new"]
    if field == "verdict":
        _replace_top_level_scalar(fm_lines, "verdict", new_value)
    elif field == "trust_level":
        _replace_nested_scalar(fm_lines, "evidence_trust", "trust_level", new_value)
    elif field == "validation.result":
        _replace_nested_scalar(fm_lines, "validation", "result", new_value)
    elif field == "validation.tier":
        _replace_nested_scalar(fm_lines, "validation", "tier", new_value)


def _replace_top_level_scalar(fm_lines, key, new_value):
    pattern = re.compile(r"^(\s*)" + re.escape(key) + r":\s*(.*)$")
    for index, line in enumerate(fm_lines):
        m = pattern.match(line)
        if m and m.group(1) == "":
            fm_lines[index] = "{}: {}".format(key, new_value)
            return


def _replace_nested_scalar(fm_lines, parent, child, new_value):
    parent_idx = _find_parent_block(fm_lines, parent)
    if parent_idx is None:
        return
    child_idx = _find_child_line(fm_lines, parent_idx, child)
    if child_idx is None:
        return
    # preserve the original indentation
    original = fm_lines[child_idx]
    indent = original[:len(original) - len(original.lstrip())]
    fm_lines[child_idx] = "{}{}: {}".format(indent, child, new_value)


def _apply_add_field(fm_lines, action):
    field = action["field"]
    parent, child = field.split(".", 1)
    parent_idx = _find_parent_block(fm_lines, parent)
    if parent_idx is None:
        # Parent block itself is missing; cannot safely add. Leave to manual.
        return
    if _find_child_line(fm_lines, parent_idx, child) is not None:
        return  # already present
    # Insert at the end of the parent block, matching its children's indent.
    parent_indent = len(fm_lines[parent_idx]) - len(fm_lines[parent_idx].lstrip())
    child_indent = "  " * (parent_indent // 2 + 1)
    insert_at = parent_idx + 1
    while insert_at < len(fm_lines):
        line = fm_lines[insert_at]
        if not line.strip():
            insert_at += 1
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= parent_indent:
            break
        insert_at += 1
    fm_lines.insert(insert_at, "{}{}: {}".format(child_indent, child, action["new"]))


def reassemble(content, new_fm_lines):
    """Rebuild the document: same leading lines, new frontmatter, same body."""
    bounds = _split_frontmatter(content)
    if bounds is None:
        return None
    fm_lines, _body, start, end = bounds
    lines = content.splitlines()
    head = lines[:start + 1]  # includes opening '---'
    tail = lines[end:]        # includes closing '---' and body
    return "\n".join(head + new_fm_lines + tail) + ("\n" if content.endswith("\n") else "")


def _atomic_write(path, content):
    """Atomically write content to path (temp + os.replace).

    Returns None on success, or an error string on failure. The temp file is
    always cleaned up on failure.
    """
    import tempfile
    tmp_fd = None
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=os.path.basename(path) + ".",
            suffix=".tmp",
            dir=os.path.dirname(path),
            text=True,
        )
        with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        tmp_fd = None
        os.replace(tmp_path, path)
        tmp_path = None
        return None
    except OSError as exc:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        return "failed to write {}: {}".format(path, exc)
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def analyze(report_path, task_path=None):
    """Return a diagnosis dict for a report file.

    Keys: valid, reasons, actions, manual, unfixable, task_cross_check.
    """
    if not os.path.isfile(report_path):
        return {"error": "report not found: {}".format(report_path)}
    content, err = _read_text(report_path)
    if err:
        return {"error": err}
    data, body, errs = extract_structured_frontmatter(report_path)
    if errs:
        return {
            "valid": False,
            "parse_errors": errs,
            "reasons": ["parse error: {}".format("; ".join(errs))],
            "actions": [],
            "manual": [],
            "unfixable": [],
        }
    if not data:
        return {
            "valid": False,
            "reasons": ["no frontmatter" if data is None else "empty frontmatter"],
            "actions": [],
            "manual": [],
            "unfixable": [],
        }
    if data.get("schema") != "agent-file-coordination/report":
        return {
            "valid": False,
            "reasons": ["wrong schema: {}".format(data.get("schema"))],
            "actions": [],
            "manual": [],
            "unfixable": ["wrong schema: not an AFC report"],
        }

    task = None
    task_cross_check = False
    if task_path:
        if not os.path.isfile(task_path):
            return {"error": "task not found: {}".format(task_path)}
        from afc_frontmatter import parse_frontmatter_nested
        task, task_err = parse_frontmatter_nested(task_path, strict=False)
        if task_err:
            return {"error": "task parse error: {}".format(task_err)}
        task_cross_check = True

    valid, reasons = validate_report_schema(data, body=body, task=task)

    bounds = _split_frontmatter(content)
    fm_lines = bounds[0] if bounds else []
    actions, manual = build_plan(reasons, fm_lines)

    unfixable = []
    for reason in manual:
        lowered = reason.lower()
        if "dangerous phrase" in lowered:
            unfixable.append(reason)
        elif reason in UNFIXABLE_HINTS:
            unfixable.append(reason)

    return {
        "valid": valid,
        "reasons": reasons,
        "actions": actions,
        "manual": manual,
        "unfixable": unfixable,
        "task_cross_check": task_cross_check,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose and (with --write) repair a rejected report's "
            "frontmatter. Default is dry-run; never edits the report body."
        )
    )
    parser.add_argument("report", help="path to the rejected report .md file")
    parser.add_argument("--task", help="optional task .md for cross-checks")
    parser.add_argument(
        "--write",
        action="store_true",
        help="apply the proposed frontmatter fix (default: dry-run only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of human text",
    )
    args = parser.parse_args(argv)

    report_path = os.path.abspath(args.report)
    task_path = os.path.abspath(args.task) if args.task else None

    result = analyze(report_path, task_path=task_path)
    if "error" in result:
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("error: {}".format(result["error"]), file=sys.stderr)
        return 2

    valid = result["valid"]
    actions = result["actions"]
    manual = result["manual"]
    unfixable = result["unfixable"]
    reasons = result["reasons"]

    has_unfixable = bool(unfixable) or any(
        "dangerous phrase" in r.lower() for r in reasons
    )

    if args.json:
        written = False
        post_valid = valid
        if (
            args.write
            and not valid
            and actions
            and not has_unfixable
        ):
            content, werr = _read_text(report_path)
            if werr:
                payload = {"error": werr}
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                return 2
            bounds = _split_frontmatter(content)
            if bounds is None:
                payload = {"error": "report has no frontmatter block to repair"}
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                return 2
            new_fm = apply_actions(bounds[0], actions)
            new_content = reassemble(content, new_fm)
            rc = _atomic_write(report_path, new_content)
            if rc is not None:
                payload = {"error": rc}
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                return 2
            written = True
            post = analyze(report_path, task_path=task_path)
            post_valid = post.get("valid", False)
        payload = {
            "report": report_path,
            "valid": post_valid,
            "was_valid": valid,
            "task_cross_check": result.get("task_cross_check", False),
            "reasons": reasons,
            "actions": actions,
            "manual": manual,
            "unfixable": unfixable,
            "would_write": (
                not valid and bool(actions) and not has_unfixable
            ),
            "written": written,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    # --- Human-readable output ---
    print("Report: {}".format(report_path))
    if result.get("parse_errors"):
        print("PARSE ERRORS:")
        for err in result["parse_errors"]:
            print("  - {}".format(err))
        return 2

    if valid:
        print("ALREADY_VALID: no repair needed.")
        return 0

    print("REJECTED reasons:")
    for reason in reasons:
        print("  - {}".format(reason))

    if has_unfixable:
        print("")
        print("NOT AUTO-REPAIRABLE (safety/structural):")
        for reason in unfixable:
            hint = UNFIXABLE_HINTS.get(reason, "")
            line = "  - {}".format(reason)
            if hint:
                line += "  -> {}".format(hint)
            print(line)
        if args.write:
            print("")
            print("--write refused: report has unfixable issues. Fix manually.")
            return 2

    if actions:
        print("")
        print("Proposed frontmatter fix{}:".format(
            " (DRY-RUN, no write)" if not args.write else ""
        ))
        for action in actions:
            if action["kind"] == "enum":
                print("  {}: {} -> {}".format(
                    action["field"], action["old"], action["new"]))
            else:
                print("  {}: (add) {}".format(action["field"], action["new"]))
        if manual:
            remaining = [m for m in manual if m not in unfixable]
            if remaining:
                print("")
                print("Left for manual judgment (not auto-fixed):")
                for reason in remaining:
                    print("  - {}".format(reason))
        if not args.write:
            print("")
            print("Apply with: afc-repair-report.py --write {}".format(report_path))
            return 0
    elif not has_unfixable:
        print("")
        print("No unambiguous frontmatter fix available; all issues need manual edits.")
        for reason in manual:
            print("  - {}".format(reason))
        return 0
    else:
        # Unfixable issues and no auto-fixable actions: nothing to write.
        if not args.write:
            return 0
        # args.write with only unfixable issues was already handled above
        # (has_unfixable block returns 2); defensive guard.
        return 2

    # --- --write path (only reached with actions and args.write) ---
    if not args.write:
        return 0
    if has_unfixable:
        print("")
        print("--write refused: report has unfixable issues. Fix manually.")
        return 2
    if not actions:
        return 0

    content, err = _read_text(report_path)
    if err:
        print("error: {}".format(err), file=sys.stderr)
        return 2
    bounds = _split_frontmatter(content)
    if bounds is None:
        print("error: report has no frontmatter block to repair", file=sys.stderr)
        return 2
    fm_lines = bounds[0]
    new_fm = apply_actions(fm_lines, actions)
    new_content = reassemble(content, new_fm)
    if new_content is None:
        print("error: could not reassemble report", file=sys.stderr)
        return 2

    werr = _atomic_write(report_path, new_content)
    if werr is not None:
        print("error: {}".format(werr), file=sys.stderr)
        return 2

    # Re-validate to confirm the fix took.
    post = analyze(report_path, task_path=task_path)
    if post.get("valid"):
        print("")
        print("REPAIRED: {} frontmatter now valid.".format(report_path))
        return 0
    post_reasons = post.get("reasons") or []
    print("")
    print("REPAIRED with remaining issues:" if post_reasons else "REPAIRED.")
    for reason in post_reasons:
        print("  remaining: {}".format(reason))
    return 0


if __name__ == "__main__":
    sys.exit(main())
