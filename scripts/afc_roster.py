"""Read-only roster usability checks for external AFC dispatch."""

import json
import os
import re
import sys


VALID_CALS = {"CAL-1", "CAL-2", "CAL-3"}
PLACEHOLDER_RE = re.compile(r"<[^>\n]+>")
SESSION_RE = re.compile(r"<!--\s*SESSION PREFERENCES\s*\n(.*?)-->", re.DOTALL)
INTERNAL_ROUTE_PATTERNS = [
    re.compile(r"\bcurrent[- ]session\s+subagent\b", re.IGNORECASE),
    re.compile(r"\bbuilt[- ]in\s+subagent\b", re.IGNORECASE),
    re.compile(r"\binternal\s+subagent\b", re.IGNORECASE),
    re.compile(r"\bbuilt[- ]in\s+helper\b", re.IGNORECASE),
    re.compile(r"\binternal\s+helper\b", re.IGNORECASE),
    re.compile(r"\btask\s+tool\b", re.IGNORECASE),
    re.compile(r"\b(?:collaboration\.)?spawn_agent\b", re.IGNORECASE),
    re.compile(r"\bmulti_agent(?:\.spawn_agent)?\b", re.IGNORECASE),
    re.compile(r"\bcoordinator\s+runtime\b", re.IGNORECASE),
    re.compile(r"\bchat[- ]only\s+call\s+inside\s+coordinator\s+runtime\b", re.IGNORECASE),
]
ROUTE_FIELDS = [
    "Tool",
    "Model",
    "Provider / Access Path",
    "Protocol Mode",
    "Best Use",
    "Avoid",
    "Notes",
]

# --- Install-local roster source of truth --------------------------------
# Resolution order (see docs/review-findings/install-local-global-roster-
# source-of-truth-requirement-20260630.md):
#   1. explicit --roster-file / AFC_ROSTER_FILE
#   2. project .agent-inbox/AGENT_ROSTER.md marked project-override
#   3. install-local LOCAL_ROSTER.md (skill root)
#   4. legacy fallback: unmarked project AGENT_ROSTER.md (only when LOCAL absent)
#   5. missing -> block external dispatch
PROJECT_OVERRIDE_MARKER = "AFC_ROSTER_SCOPE: project-override"
# The marker must sit on its own dedicated single-line HTML comment line so
# documentation examples inside multi-line comment blocks in TEMPLATE_ROSTER.md
# do not accidentally activate override. Match: optional whitespace, then the
# canonical single-line HTML comment carrying only the marker.
PROJECT_OVERRIDE_MARKER_RE = re.compile(
    r"^\s*<!--\s*" + re.escape(PROJECT_OVERRIDE_MARKER) + r"\s*-->\s*$",
    re.MULTILINE,
)


def skill_root():
    """Installed Skill root. AFC_SKILL_ROOT overrides (for tests/dev);
    otherwise the parent of this script's scripts/ directory."""
    env_root = os.environ.get("AFC_SKILL_ROOT")
    if env_root:
        return os.path.abspath(env_root)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def local_roster_path():
    return os.path.join(skill_root(), "LOCAL_ROSTER.md")


def local_recipes_path():
    return os.path.join(skill_root(), "LOCAL_INVOKE_RECIPES.json")


def _has_project_override_marker(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            return bool(PROJECT_OVERRIDE_MARKER_RE.search(handle.read()))
    except OSError:
        return False


def resolve_roster(inbox_dir, explicit_roster_file=None, allow_project_override=True):
    """Resolve the dispatch roster path. Returns (path_or_None, source).

    source is one of: explicit, project-override, install-local,
    project-legacy-fallback, missing.
    """
    explicit = explicit_roster_file or os.environ.get("AFC_ROSTER_FILE")
    if explicit:
        return explicit, "explicit"
    project_path = os.path.join(inbox_dir, "AGENT_ROSTER.md")
    project_exists = os.path.isfile(project_path)
    if allow_project_override and project_exists and _has_project_override_marker(project_path):
        return project_path, "project-override"
    local_path = local_roster_path()
    if os.path.isfile(local_path):
        return local_path, "install-local"
    if project_exists:
        return project_path, "project-legacy-fallback"
    return None, "missing"


def resolve_recipes(inbox_dir, explicit_recipes_file=None, roster_source=None):
    """Resolve CAL-3 invoke recipes path. Returns (path_or_None, source).

    source is one of: explicit, project-override, project-legacy,
    install-local, missing. When the roster_source is project-scoped
    (project-override or project-legacy-fallback) recipe resolution stays
    within the same scope: the project's own invoke-recipes.json is
    required, and no fall-through to install-local recipes is allowed.
    A project-scoped roster with no project recipe means CAL-3 has no
    binding for this project — the gate must block, not silently borrow
    an install-local recipe with a coincidentally matching agent name.
    """
    explicit = explicit_recipes_file or os.environ.get("AFC_INVOKE_RECIPES_FILE")
    if explicit:
        return explicit, "explicit"
    project_path = os.path.join(inbox_dir, "invoke-recipes.json")
    project_scoped = roster_source in ("project-override", "project-legacy-fallback")
    if project_scoped:
        if os.path.isfile(project_path):
            return project_path, (
                "project-override" if roster_source == "project-override" else "project-legacy"
            )
        # Fail closed within scope: do NOT fall through to install-local.
        return None, "missing"
    local_path = local_recipes_path()
    if os.path.isfile(local_path):
        return local_path, "install-local"
    if os.path.isfile(project_path):
        return project_path, "project-legacy"
    return None, "missing"


def parse_session_preferences(roster_text):
    m = SESSION_RE.search(roster_text or "")
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
        "Capability limits": "capability_limits",
        "Smoke tests": "smoke_tests",
        "Confirmed": "confirmed",
    }
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("Change policy"):
            continue
        for label, key in field_map.items():
            if line.startswith(label + ":"):
                prefs[key] = line[len(label) + 1:].strip()
                break
    return prefs


def is_cal_configured(prefs):
    cal = prefs.get("default_cal", "").strip()
    return cal in VALID_CALS and not PLACEHOLDER_RE.search(cal)


def _split_row(line):
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return []
    return [cell.strip() for cell in line.strip("|").split("|")]


def parse_roster_rows(roster_text):
    rows = []
    headers = None
    for line in (roster_text or "").splitlines():
        cells = _split_row(line)
        if not cells:
            continue
        if all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        if headers is None:
            lowered = [cell.lower() for cell in cells]
            if "agent name" in lowered and "role" in lowered:
                headers = cells
            continue
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)))
        rows.append(dict(zip(headers, cells)))
    return rows


def _cell(row, name):
    for key, value in row.items():
        if key.strip().lower() == name.lower():
            return str(value or "").strip()
    return ""


def _has_placeholder(value):
    return bool(PLACEHOLDER_RE.search(str(value or "")))


def _concrete(value):
    text = str(value or "").strip()
    return bool(text) and not _has_placeholder(text) and text.lower() not in {
        "unknown",
        "n/a",
        "none",
        "todo",
    }


def internal_route_reason(row):
    text = " | ".join(_cell(row, field) for field in ROUTE_FIELDS)
    for pattern in INTERNAL_ROUTE_PATTERNS:
        match = pattern.search(text)
        if match:
            return "worker '{}' uses invalid internal route marker: {}".format(
                _cell(row, "Agent Name") or "<unknown>",
                match.group(0),
            )
    return ""


def is_external_worker_row(row):
    role = _cell(row, "Role").lower()
    authority = _cell(row, "Coordinator Authority").lower()
    agent = _cell(row, "Agent Name")
    if not _concrete(agent):
        return False
    # Fail closed: a worker route must explicitly deny coordinator authority.
    # Empty, non-standard, or truthy variants are incomplete roster data, not
    # proof that the route is external and bounded.
    if role == "coordinator" or authority != "no":
        return False
    if internal_route_reason(row):
        return False
    return True


def _row_is_user_relay_usable(row):
    required = [
        "Agent Name",
        "Role",
        "Tool",
        "Model",
        "Provider / Access Path",
        "Protocol Mode",
        "Can Edit",
        "Can Run Commands",
        "Can Write Reports",
        "Best Use",
    ]
    for field in required:
        if not _concrete(_cell(row, field)):
            return False
    if _cell(row, "Can Write Reports").lower() not in {"yes", "bounded"}:
        return False
    return True


def _load_recipes(inbox_dir, recipe_file=None):
    path = recipe_file or os.path.join(inbox_dir, "invoke-recipes.json")
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _probe_verified(recipe_id, recipe, recipes_data):
    if recipe.get("probe_verified") is True:
        return True
    probes = recipes_data.get("probes")
    if not isinstance(probes, list):
        return False
    recipe_tool = str(recipe.get("tool") or recipe_id).strip().lower()
    for probe in probes:
        if not isinstance(probe, dict) or probe.get("available") is not True:
            continue
        probe_tool = str(probe.get("tool") or probe.get("recipe_id") or "").strip().lower()
        if probe_tool in {recipe_id.lower(), recipe_tool}:
            return True
    return False


def cal3_callable_routes(inbox_dir, worker_names=None, recipe_file=None):
    data = _load_recipes(inbox_dir, recipe_file=recipe_file)
    agent_map = data.get("agent_recipes", {})
    recipes = data.get("recipes", {})
    if not isinstance(agent_map, dict) or not isinstance(recipes, dict):
        return 0
    names = None if worker_names is None else {
        str(name).strip().lower() for name in worker_names if str(name).strip()
    }
    count = 0
    for agent_name, recipe_id in agent_map.items():
        if names is not None and str(agent_name).strip().lower() not in names:
            continue
        recipe_id = str(recipe_id or "").strip()
        recipe = recipes.get(recipe_id) or recipes.get(recipe_id.lower())
        if not isinstance(recipe, dict):
            continue
        if not isinstance(recipe.get("argv"), list) or not recipe.get("argv"):
            continue
        if _probe_verified(recipe_id, recipe, data):
            count += 1
    return count


def roster_status(inbox_dir, require_cal3=False, agent_name=None, recipe_file=None, explicit_roster_file=None):
    roster_path, roster_source = resolve_roster(inbox_dir, explicit_roster_file=explicit_roster_file)
    base = {
        "roster_status": "missing",
        "roster_source": roster_source,
        "roster_path": roster_path or "",
        "external_worker_routes": 0,
        "cal_default_recorded": "no",
        "cal3_callable_routes": 0,
        "blocking_reason": "LOCAL_ROSTER.md not found in installed Skill directory",
        "recommended_next_action": "configure_local_roster",
    }
    if not roster_path or not os.path.isfile(roster_path):
        return base
    try:
        with open(roster_path, "r", encoding="utf-8-sig") as handle:
            text = handle.read()
    except OSError as exc:
        base["roster_status"] = "incomplete"
        base["blocking_reason"] = "could not read roster: {}".format(exc)
        return base
    if not text.strip():
        base["roster_status"] = "incomplete"
        base["blocking_reason"] = "resolved roster is empty"
        return base

    prefs = parse_session_preferences(text)
    cal_recorded = is_cal_configured(prefs)
    rows = parse_roster_rows(text)
    candidate_rows = [row for row in rows if is_external_worker_row(row)]
    invalid_internal_rows = [
        row for row in rows
        if _cell(row, "Role").lower() != "coordinator"
        and _cell(row, "Coordinator Authority").lower() != "yes"
        and internal_route_reason(row)
    ]
    if agent_name:
        invalid_internal_rows = [
            row for row in invalid_internal_rows
            if _cell(row, "Agent Name").lower() == agent_name.lower()
        ]
    external_rows = [
        row for row in candidate_rows
        if _row_is_user_relay_usable(row)
    ]
    if agent_name:
        external_rows = [
            row for row in external_rows
            if _cell(row, "Agent Name").lower() == agent_name.lower()
        ]
    worker_names = [_cell(row, "Agent Name") for row in external_rows]
    resolved_recipe = recipe_file if recipe_file is not None else resolve_recipes(
        inbox_dir, roster_source=roster_source
    )[0]
    cal3_count = cal3_callable_routes(
        inbox_dir,
        # Generic CAL-3 readiness must still count only recipes bound to usable
        # external roster rows. Otherwise an unrelated GhostWorker recipe can
        # make an uncallable roster look ready.
        worker_names=worker_names,
        recipe_file=resolved_recipe,
    )
    status = dict(base)
    status.update({
        "external_worker_routes": len(external_rows),
        "cal_default_recorded": "yes" if cal_recorded else "no",
        "cal3_callable_routes": cal3_count,
    })

    if PLACEHOLDER_RE.search(text) and not external_rows:
        status["roster_status"] = "placeholder_only"
        status["blocking_reason"] = "resolved roster still contains only template placeholder routes"
        return status
    if invalid_internal_rows:
        status["roster_status"] = "incomplete"
        status["blocking_reason"] = internal_route_reason(invalid_internal_rows[0])
        return status
    if not cal_recorded:
        status["roster_status"] = "incomplete"
        status["blocking_reason"] = "default CAL is missing or still a placeholder"
        return status
    if not external_rows:
        status["roster_status"] = "incomplete"
        if agent_name:
            status["blocking_reason"] = "worker '{}' is not a usable external roster route".format(agent_name)
        else:
            status["blocking_reason"] = "no usable external worker route is recorded"
        return status
    if require_cal3:
        if cal3_count <= 0:
            status["roster_status"] = "incomplete"
            status["blocking_reason"] = "CAL-3 requires a callable, probe-verified invoke recipe"
            return status

    status["roster_status"] = "usable"
    status["blocking_reason"] = ""
    status["recommended_next_action"] = "dispatch_allowed"
    if roster_source == "project-legacy-fallback":
        status["warning"] = (
            "Using legacy project AGENT_ROSTER.md because LOCAL_ROSTER.md is "
            "missing. Configure LOCAL_ROSTER.md to avoid per-project roster "
            "duplication."
        )
    return status


def format_roster_block(status):
    lines = [
        "ROSTER_BLOCKED: external dispatch requires roster_status=usable",
        "roster_status: {}".format(status.get("roster_status", "")),
        "roster_source: {}".format(status.get("roster_source", "")),
        "roster_path: {}".format(status.get("roster_path", "")),
        "external_worker_routes: {}".format(status.get("external_worker_routes", 0)),
        "cal_default_recorded: {}".format(status.get("cal_default_recorded", "no")),
        "cal3_callable_routes: {}".format(status.get("cal3_callable_routes", 0)),
        "blocking_reason: {}".format(status.get("blocking_reason", "")),
        "recommended_next_action: {}".format(status.get("recommended_next_action", "ask_roster")),
        "Please confirm default CAL, available external workers/tools/models, route availability, preference order, avoid list, permissions, report-writing ability, and CAL-3 bindings/probes if applicable.",
    ]
    return "\n".join(lines)


def maybe_warn_roster(status, stream=None):
    """Print a roster warning (e.g. legacy-fallback nudge) if present."""
    warning = (status or {}).get("warning")
    if warning:
        print(warning, file=stream or sys.stderr)


def require_usable_roster(inbox_dir, agent_name=None, require_cal3=False, recipe_file=None, explicit_roster_file=None):
    status = roster_status(
        inbox_dir,
        require_cal3=require_cal3,
        agent_name=agent_name,
        recipe_file=recipe_file,
        explicit_roster_file=explicit_roster_file,
    )
    if status.get("roster_status") == "usable":
        return True, status
    return False, status
