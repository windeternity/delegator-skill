#!/usr/bin/env python3
"""First-run configuration helper for Delegator.

Reads/updates the SESSION PREFERENCES block in .agent-inbox/AGENT_ROSTER.md
and appends a ROSTER_UPDATED event to events.jsonl.

Python stdlib only. Python 3.8+ compatible.

Usage:
    # Check if CAL default is already configured (exit 0 = configured, 1 = not)
    python -B scripts/afc-first-run-config.py --inbox .agent-inbox --check-only

    # Print the standard first-run questionnaire
    python -B scripts/afc-first-run-config.py --print-questionnaire

    # Write configuration
    python -B scripts/afc-first-run-config.py --inbox .agent-inbox \\
        --default-cal CAL-2 \\
        --resources "Claude Code CLI, codex CLI" \\
        --available-now "worker-cli, backup-cli" \\
        --model-order "primary-model, review-model, fallback-model" \\
        --avoid "deprecated-model (unavailable)" \\
        --capability-limits "no browser automation" \\
        --confirmed-at 2026-06-27
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CALS = {"CAL-1", "CAL-2", "CAL-3"}

# Patterns that look like secrets or sensitive data.
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd|pwd)\s*[:=]"),
    re.compile(r"(?i)(sk-[a-zA-Z0-9]{20,})"),             # OpenAI-style key
    re.compile(r"(?i)(ghp_[a-zA-Z0-9]{20,})"),             # GitHub token
    re.compile(r"(?i)(xoxb-[a-zA-Z0-9-]+)"),               # Slack token
    re.compile(r"(?i)(AKIA[0-9A-Z]{16})"),                  # AWS access key
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9._-]{20,}"),       # Bearer token
    re.compile(r"(?i)https?://[^\s]+@(?!.*\.(com|org|io))"),  # URL with auth
]

QUESTIONNAIRE = """\
Session Bootstrap:
- Existing resources: <tools/models/accounts/runtimes you already have>
- Available now: <usable workers, CLIs, providers, local runtimes>
- Model preference order: <preferred models and fallbacks>
- Avoid / unavailable: <models or routes to avoid, with reason>
- Capability limits: <anything the agent must not assume>
- CAL preference: <CAL-1 | CAL-2 | CAL-3>
  CAL-1  Manual Relay — you paste handoffs, any worker works
  CAL-2  Auto Intake — you paste handoff, coordinator auto-detects report
  CAL-3  Full Auto — coordinator launches workers via local CLI (requires CLI verification)
- Record these as this project's default until I ask to change them?
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def looks_like_secret(text):
    """Return True if *text* matches a known secret pattern."""
    for pat in SECRET_PATTERNS:
        if pat.search(text):
            return True
    return False


def redact_secrets(text):
    """Replace secret-looking tokens with [REDACTED]. Returns (cleaned, found)."""
    found = []
    cleaned = text
    for pat in SECRET_PATTERNS:
        for m in pat.finditer(cleaned):
            found.append(m.group())
            cleaned = cleaned.replace(m.group(), "[REDACTED]", 1)
    return cleaned, found


def next_event_id(events_path):
    """Read events.jsonl and return the next sequential event_id."""
    max_num = 0
    if os.path.isfile(events_path):
        with open(events_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(evt, dict):
                    continue
                eid = evt.get("event_id", "")
                m = re.match(r"evt-(\d+)", eid)
                if m:
                    max_num = max(max_num, int(m.group(1)))
    return "evt-{:03d}".format(max_num + 1)


def parse_session_preferences(roster_text):
    """Parse the SESSION PREFERENCES HTML comment block.

    Returns a dict of key->value (stripped), or empty dict if block not found.
    Keys are lowercased field names: default_cal, execution_preference, etc.
    """
    # Match the comment block
    m = re.search(
        r"<!--\s*SESSION PREFERENCES\s*\n(.*?)-->",
        roster_text,
        re.DOTALL,
    )
    if not m:
        return {}
    block = m.group(1)
    prefs = {}
    field_map = {
        "Default CAL": "default_cal",
        "Execution preference": "execution_preference",
        "Available resources": "available_resources",
        "Available now": "available_now",
        "Model preference order": "model_preference_order",
        "Avoid / unavailable": "avoid_unavailable",
        "Smoke tests": "smoke_tests",
        "Confirmed": "confirmed",
    }
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("Change policy"):
            continue
        for label, key in field_map.items():
            if line.startswith(label + ":"):
                value = line[len(label) + 1:].strip()
                prefs[key] = value
                break
    return prefs


def is_configured(prefs):
    """Return True if SESSION PREFERENCES has a non-placeholder CAL default."""
    cal = prefs.get("default_cal", "")
    if not cal:
        return False
    # Treat template placeholders as unconfigured
    if "CAL-1_OR_CAL-2_OR_CAL-3" in cal or "<" in cal:
        return False
    return cal in VALID_CALS


def build_preferences_block(default_cal, resources, available_now,
                            model_order, avoid, capability_limits,
                            confirmed_at):
    """Build the SESSION PREFERENCES HTML comment block text."""
    lines = [
        "<!-- SESSION PREFERENCES",
        "Default CAL: {}".format(default_cal),
        "Execution preference: {}".format(model_order or "<PREFERRED_AGENT_TOOL_MODEL_PAIRS_AND_AVOID_LIST>"),
        "Available resources: {}".format(resources or "<TOOLS_PROVIDERS_ACCOUNTS_LOCAL_RUNTIMES_AND_LIMITS>"),
        "Available now: {}".format(available_now or "<USABLE_WORKERS_CLIS_PROVIDERS_LOCAL_RUNTIMES>"),
        "Model preference order: {}".format(model_order or "<PREFERRED_MODELS_AND_FALLBACKS>"),
        "Avoid / unavailable: {}".format(avoid or "<MODELS_TO_AVOID_PAUSED_ROUTES_OR_KNOWN_LIMITS>"),
        "Capability limits: {}".format(capability_limits or "<CAPABILITY_LIMITS>"),
        "Smoke tests: <LAST_KNOWN_SMALL_TEST_OR_UNKNOWN>",
        "Confirmed: {}".format(confirmed_at),
        "Change policy: keep these defaults until the user asks to change them or a route becomes unavailable.",
        "-->",
    ]
    return "\n".join(lines)


def update_roster(roster_text, preferences_block):
    """Replace or insert the SESSION PREFERENCES block in roster text."""
    pattern = re.compile(
        r"<!--\s*SESSION PREFERENCES\s*\n.*?-->",
        re.DOTALL,
    )
    if pattern.search(roster_text):
        return pattern.sub(preferences_block, roster_text, count=1)
    # Insert after the frontmatter closing line and the # heading
    lines = roster_text.split("\n")
    insert_idx = 0
    found_frontmatter_end = False
    for i, line in enumerate(lines):
        if found_frontmatter_end and line.strip().startswith("# "):
            insert_idx = i + 1
            # Skip blank lines after heading
            while insert_idx < len(lines) and not lines[insert_idx].strip():
                insert_idx += 1
            break
        if line.strip() == "---" and i > 0:
            found_frontmatter_end = True
    if insert_idx == 0:
        # Fallback: insert after first heading
        for i, line in enumerate(lines):
            if line.strip().startswith("# "):
                insert_idx = i + 1
                break
    lines.insert(insert_idx, "")
    for j, pline in enumerate(preferences_block.split("\n")):
        lines.insert(insert_idx + 1 + j, pline)
    lines.insert(insert_idx + 1 + len(preferences_block.split("\n")), "")
    return "\n".join(lines)


# Indicator keyword sets per CAL, matched on word boundaries (see
# _matches_indicator) rather than as bare substrings, so 'cli' inside 'client'
# or a bare 'auto' inside 'auto intake' cannot trip the wrong branch. Priority
# is explicit and ordered: CAL-2 (foreground watcher) outranks CAL-3 (callable
# CLI), which outranks the CAL-1 safe default.
CAL2_INDICATORS = ("watcher", "foreground", "auto intake", "cal-2")
CAL3_INDICATORS = (
    "cli", "command line", "headless", "dispatch", "auto-dispatch", "cal-3",
)


def _matches_indicator(text, indicators):
    """True if any indicator appears in *text* on word boundaries.

    Word-boundary matching means 'cli' matches the standalone token 'cli' (or
    'CLI') but not the substring inside 'client', and a multi-word phrase like
    'auto intake' is matched as a unit instead of via a bare 'auto'.
    """
    return any(
        re.search(r"\b" + re.escape(indicator) + r"\b", text)
        for indicator in indicators
    )


def recommend_cal(resources, available_now):
    """Return (recommended_cal, reason) based on conservative rules.

    Indicators are matched on word boundaries; priority is CAL-2, then CAL-3,
    then the CAL-1 safe default.
    """
    combined = "{} {}".format(
        (available_now or "").lower(), (resources or "").lower()
    )
    if _matches_indicator(combined, CAL2_INDICATORS):
        return "CAL-2", ("foreground watcher available; CAL-2 auto-detects "
                         "reports without manual 'done' signal")
    if _matches_indicator(combined, CAL3_INDICATORS):
        return "CAL-3", ("callable CLI detected in resources; CAL-3 enables "
                         "auto-dispatch but requires CLI verification before "
                         "first dispatch")
    return "CAL-1", ("no callable CLI or watcher detected; CAL-1 is the "
                     "safe default — you relay handoffs manually")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_check_only(inbox_dir):
    """Check if SESSION PREFERENCES has a valid CAL default. Exit 0=yes, 1=no."""
    roster_path = os.path.join(inbox_dir, "AGENT_ROSTER.md")
    if not os.path.isfile(roster_path):
        print("NOT_CONFIGURED")
        print("reason: AGENT_ROSTER.md not found")
        return 1
    with open(roster_path, "r", encoding="utf-8") as f:
        text = f.read()
    prefs = parse_session_preferences(text)
    if is_configured(prefs):
        print("CONFIGURED")
        print("default_cal: {}".format(prefs.get("default_cal", "")))
        print("confirmed: {}".format(prefs.get("confirmed", "")))
        return 0
    else:
        print("NOT_CONFIGURED")
        if prefs:
            print("default_cal: {}".format(prefs.get("default_cal", "<unset>")))
        return 1


def cmd_print_questionnaire():
    """Print the standard first-run questionnaire block."""
    print(QUESTIONNAIRE)
    return 0


def cmd_write(inbox_dir, default_cal, resources, available_now,
              model_order, avoid, capability_limits, confirmed_at):
    """Write configuration into AGENT_ROSTER.md and append event."""
    # Validate CAL
    if default_cal not in VALID_CALS:
        print("ERROR: invalid CAL '{}'. Must be one of: {}".format(
            default_cal, ", ".join(sorted(VALID_CALS))), file=sys.stderr)
        return 1

    # Validate confirmed_at date
    try:
        datetime.strptime(confirmed_at, "%Y-%m-%d")
    except ValueError:
        print("ERROR: invalid date '{}'. Expected YYYY-MM-DD.".format(
            confirmed_at), file=sys.stderr)
        return 1

    # Scan all user-provided values for secrets
    all_values = [resources or "", available_now or "", model_order or "",
                  avoid or "", capability_limits or ""]
    for val in all_values:
        if looks_like_secret(val):
            cleaned, found = redact_secrets(val)
            print("ERROR: input contains secret-looking data. "
                  "Secrets must not be recorded. Found: {}".format(
                      ", ".join(repr(f[:20] + "...") for f in found)),
                  file=sys.stderr)
            return 1

    # Ensure inbox exists
    if not os.path.isdir(inbox_dir):
        print("ERROR: inbox directory not found: {}".format(inbox_dir),
              file=sys.stderr)
        return 1

    roster_path = os.path.join(inbox_dir, "AGENT_ROSTER.md")
    if not os.path.isfile(roster_path):
        print("ERROR: AGENT_ROSTER.md not found in {}".format(inbox_dir),
              file=sys.stderr)
        return 1

    # Read existing roster
    with open(roster_path, "r", encoding="utf-8") as f:
        roster_text = f.read()

    # Build new preferences block
    prefs_block = build_preferences_block(
        default_cal, resources, available_now,
        model_order, avoid, capability_limits, confirmed_at,
    )

    # Update roster
    new_roster = update_roster(roster_text, prefs_block)

    # Write roster atomically (simple write; afc_fsutil is in scripts/ but
    # we keep this script dependency-free for portability)
    tmp_path = roster_path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_roster)
        os.replace(tmp_path, roster_path)
    except OSError:
        # Fallback: direct write
        try:
            with open(roster_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_roster)
        except OSError as e:
            print("ERROR: failed to write AGENT_ROSTER.md: {}".format(e),
                  file=sys.stderr)
            return 1
        finally:
            if os.path.isfile(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # Append ROSTER_UPDATED event
    events_path = os.path.join(inbox_dir, "events.jsonl")
    event = {
        "schema": "agent-file-coordination/event",
        "schema_version": "0.1.0",
        "event_id": next_event_id(events_path),
        "event_type": "ROSTER_UPDATED",
        "created_at": confirmed_at,
        "summary": "First-run config: CAL={}, resources recorded.".format(
            default_cal),
    }
    try:
        with open(events_path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError as e:
        print("ERROR: failed to append event: {}".format(e), file=sys.stderr)
        return 1

    print("OK")
    print("default_cal: {}".format(default_cal))
    print("confirmed: {}".format(confirmed_at))
    print("roster: {}".format(roster_path))
    print("event: {}".format(event["event_id"]))
    return 0


def cmd_recommend(resources, available_now):
    """Print a CAL recommendation based on conservative rules."""
    cal, reason = recommend_cal(resources, available_now)
    print("recommended_cal: {}".format(cal))
    print("reason: {}".format(reason))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="First-run configuration helper for Delegator."
    )
    parser.add_argument(
        "--inbox",
        default=".agent-inbox",
        help="Path to .agent-inbox directory (default: .agent-inbox)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Check if CAL default is configured. Exit 0=yes, 1=no.",
    )
    parser.add_argument(
        "--print-questionnaire",
        action="store_true",
        help="Print the standard first-run questionnaire.",
    )
    parser.add_argument(
        "--recommend",
        action="store_true",
        help="Recommend a CAL level based on described resources.",
    )
    parser.add_argument("--default-cal", choices=sorted(VALID_CALS))
    parser.add_argument("--resources", default="")
    parser.add_argument("--available-now", default="")
    parser.add_argument("--model-order", default="")
    parser.add_argument("--avoid", default="")
    parser.add_argument("--capability-limits", default="")
    parser.add_argument("--confirmed-at", default="")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.print_questionnaire:
        return cmd_print_questionnaire()

    if args.recommend:
        return cmd_recommend(args.resources, args.available_now)

    inbox = os.path.abspath(args.inbox)

    if args.check_only:
        return cmd_check_only(inbox)

    if args.default_cal:
        confirmed = args.confirmed_at
        if not confirmed:
            confirmed = datetime.now().strftime("%Y-%m-%d")
        return cmd_write(
            inbox,
            args.default_cal,
            args.resources,
            args.available_now,
            args.model_order,
            args.avoid,
            args.capability_limits,
            confirmed,
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
