#!/usr/bin/env python3
"""Resolver fixture: install-local LOCAL_ROSTER.md source of truth.

Covers afc_roster.resolve_roster via the CLI surface
(afc-first-run-config.py --skill-root/--roster-status) and one dispatch
entrypoint (afc-cal2-arm.py). Uses AFC_SKILL_ROOT -> temp skill root and
AFC_ROSTER_FILE for explicit override; never touches real ~/.claude/~/.codex.

Usage:
    python -B examples/fixtures/afc-roster-resolver/run-tests.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
FIRST_RUN = os.path.join(REPO_ROOT, "scripts", "afc-first-run-config.py")
CAL2_ARM = os.path.join(REPO_ROOT, "scripts", "afc-cal2-arm.py")
TEMPLATE_ROSTER = os.path.join(REPO_ROOT, "templates", "TEMPLATE_ROSTER.md")

PROJECT_OVERRIDE_MARKER = "<!-- AFC_ROSTER_SCOPE: project-override -->"


class Runner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def check(self, name, ok, detail=""):
        if ok:
            self.passed += 1
            print("  [PASS] {}".format(name))
        else:
            self.failed += 1
            self.failures.append((name, detail))
            print("  [FAIL] {}: {}".format(name, detail[:300]))

    def report(self):
        print("\n" + "=" * 60)
        print("passed: {}".format(self.passed))
        print("failed: {}".format(self.failed))
        if self.failures:
            for name, detail in self.failures:
                print("  - {}: {}".format(name, detail[:200]))
        return 0 if self.failed == 0 else 1


def run_first_run(skill_root, inbox, *extra, env_extra=None, timeout=30):
    env = dict(os.environ)
    env["AFC_SKILL_ROOT"] = skill_root
    if env_extra:
        env.update(env_extra)
    cmd = [sys.executable, "-B", FIRST_RUN, "--inbox", inbox, "--roster-status"] + list(extra)
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def run_cal2_arm(skill_root, inbox, *extra, timeout=30):
    env = dict(os.environ)
    env["AFC_SKILL_ROOT"] = skill_root
    cmd = [sys.executable, "-B", CAL2_ARM, "--inbox", inbox] + list(extra)
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def make_skill():
    return tempfile.mkdtemp(prefix="afc-skill-root-")


def make_proj_inbox():
    tmp = tempfile.mkdtemp(prefix="afc-proj-")
    inbox = os.path.join(tmp, ".agent-inbox")
    os.makedirs(inbox)
    open(os.path.join(inbox, "events.jsonl"), "w").close()
    return tmp, inbox


def usable_roster(cal="CAL-2", agents=("Worker1",), override=False):
    rows = "\n".join(
        "| {a} | implementer | external-chat | user-relay-model | user-relay:{a} | task-only | no | yes | tests_only | yes | no | manual_needed | work | none | ext |".format(a=a)
        for a in agents
    )
    marker = (PROJECT_OVERRIDE_MARKER + "\n") if override else ""
    return (
        "---\nschema: agent-file-coordination/roster\nschema_version: 0.1.0\n---\n"
        + marker
        + "# Roster\n\n<!-- SESSION PREFERENCES\nDefault CAL: {cal}\nConfirmed: 2026-06-30\nChange policy: keep.\n-->\n\n"
        "| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        "| Coordinator | coordinator | codex | m | local | full-skill | yes | yes | bounded | yes | yes | can_use_existing | deco | none | c |\n"
        "{rows}\n"
    ).format(cal=cal, rows=rows)


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def parse_status(stdout):
    out = {}
    for line in stdout.splitlines():
        if ": " in line:
            k, _, v = line.partition(": ")
            out[k] = v
    return out


# --- Tests ----------------------------------------------------------------

def test_install_local_usable(runner):
    print("\n[test] usable LOCAL + no project => install-local, usable")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        write(os.path.join(skill, "LOCAL_ROSTER.md"), usable_roster())
        code, out, err = run_first_run(skill, inbox)
        s = parse_status(out)
        runner.check("exit=0", code == 0, "code={} out={!r} err={!r}".format(code, out[:200], err[:200]))
        runner.check("usable", s.get("roster_status") == "usable", out[:200])
        runner.check("install-local", s.get("roster_source") == "install-local", out[:200])
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_no_local_no_project_missing(runner):
    print("\n[test] no LOCAL + no project => missing, configure_local_roster")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        code, out, err = run_first_run(skill, inbox)
        s = parse_status(out)
        runner.check("exit=1", code == 1, "code={} out={!r}".format(code, out[:200]))
        runner.check("missing", s.get("roster_status") == "missing", out[:200])
        runner.check("source missing", s.get("roster_source") == "missing", out[:200])
        runner.check("configure_local_roster", s.get("recommended_next_action") == "configure_local_roster", out[:200])
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_local_placeholder_no_fallback(runner):
    print("\n[test] LOCAL placeholder-only + no project => not usable, no fallback")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        write(os.path.join(skill, "LOCAL_ROSTER.md"),
              "---\nschema: agent-file-coordination/roster\n---\n# R\n<!-- SESSION PREFERENCES\nDefault CAL: <CAL>\n-->\n")
        code, out, err = run_first_run(skill, inbox)
        s = parse_status(out)
        runner.check("exit=1", code == 1, "code={} out={!r}".format(code, out[:200]))
        runner.check("not usable", s.get("roster_status") != "usable", out[:200])
        runner.check("stays install-local", s.get("roster_source") == "install-local", out[:200])
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_local_shadows_unmarked_project(runner):
    print("\n[test] usable LOCAL + unmarked project => install-local wins")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        write(os.path.join(skill, "LOCAL_ROSTER.md"), usable_roster(agents=("Worker1",)))
        write(os.path.join(inbox, "AGENT_ROSTER.md"), usable_roster(cal="CAL-1", agents=("OtherWorker",)))
        code, out, err = run_first_run(skill, inbox)
        s = parse_status(out)
        runner.check("usable", s.get("roster_status") == "usable", out[:200])
        runner.check("install-local not project", s.get("roster_source") == "install-local", out[:200])
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_marked_project_override_usable(runner):
    print("\n[test] marked project override usable => project-override")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        write(os.path.join(skill, "LOCAL_ROSTER.md"), usable_roster(agents=("Worker1",)))
        write(os.path.join(inbox, "AGENT_ROSTER.md"), usable_roster(cal="CAL-1", agents=("ProjWorker",), override=True))
        code, out, err = run_first_run(skill, inbox)
        s = parse_status(out)
        runner.check("usable", s.get("roster_status") == "usable", out[:200])
        runner.check("project-override", s.get("roster_source") == "project-override", out[:200])
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_marked_project_override_incomplete_no_fallback(runner):
    print("\n[test] marked project override incomplete => block, no LOCAL fallback")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        write(os.path.join(skill, "LOCAL_ROSTER.md"), usable_roster(agents=("Worker1",)))
        write(os.path.join(inbox, "AGENT_ROSTER.md"),
              "---\nschema: agent-file-coordination/roster\n---\n" + PROJECT_OVERRIDE_MARKER + "\n# R\n<!-- SESSION PREFERENCES\nDefault CAL: <CAL>\n-->\n")
        code, out, err = run_first_run(skill, inbox)
        s = parse_status(out)
        runner.check("exit=1", code == 1, "code={} out={!r}".format(code, out[:200]))
        runner.check("not usable", s.get("roster_status") != "usable", out[:200])
        runner.check("stays project-override", s.get("roster_source") == "project-override", out[:200])
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_legacy_fallback_warning(runner):
    print("\n[test] no LOCAL + usable unmarked project => legacy fallback + warning")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        write(os.path.join(inbox, "AGENT_ROSTER.md"), usable_roster(agents=("Worker1",)))
        code, out, err = run_first_run(skill, inbox)
        s = parse_status(out)
        runner.check("usable", s.get("roster_status") == "usable", out[:200])
        runner.check("project-legacy-fallback", s.get("roster_source") == "project-legacy-fallback", out[:200])
        runner.check("warning emitted", "legacy project AGENT_ROSTER.md" in (err + out), (err + out)[:300])
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_explicit_roster_file(runner):
    print("\n[test] AFC_ROSTER_FILE explicit override")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        write(os.path.join(skill, "LOCAL_ROSTER.md"), usable_roster(cal="CAL-1", agents=("LocalWorker",)))
        explicit = os.path.join(proj, "explicit-roster.md")
        write(explicit, usable_roster(cal="CAL-2", agents=("ExplicitWorker",)))
        code, out, err = run_first_run(skill, inbox, env_extra={"AFC_ROSTER_FILE": explicit})
        s = parse_status(out)
        runner.check("usable", s.get("roster_status") == "usable", out[:200])
        runner.check("explicit source", s.get("roster_source") == "explicit", out[:200])
        runner.check("explicit path", s.get("roster_path") == explicit, out[:200])
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_cal2_arm_install_local(runner):
    print("\n[test] afc-cal2-arm install-local route allows; unrostered blocks")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        write(os.path.join(skill, "LOCAL_ROSTER.md"), usable_roster(agents=("Worker1",)))
        task = (
            "---\nschema: agent-file-coordination/task\nschema_version: 0.1.0\n"
            "task_id: t1\nagent_name: Worker1\nrole: implementer\nprotocol_mode: task-only\n"
            "coordinator_authority: no\nstatus: ASSIGNED\nreport_path: report-Worker1-t1.md\n"
            "created_at: 2026-06-30\n---\n# Task\n## Role Boundary\nx\n"
        )
        write(os.path.join(inbox, "task-Worker1-t1.md"), task)
        code, out, err = run_cal2_arm(skill, inbox, "--task-id", "t1", "--dry-run")
        runner.check("install-local arm exit=0", code == 0, "code={} err={!r}".format(code, err[:200]))
        # Ghost worker not in LOCAL roster -> blocked
        write(os.path.join(inbox, "task-Ghost-t2.md"),
              task.replace("task_id: t1", "task_id: t2").replace("agent_name: Worker1", "agent_name: GhostWorker"))
        code2, out2, err2 = run_cal2_arm(skill, inbox, "--task-id", "t2", "--dry-run")
        runner.check("unrostered agent exit!=0", code2 != 0, "code={}".format(code2))
        runner.check("ROSTER_BLOCKED", "ROSTER_BLOCKED" in err2, err2[:200])
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_recipes_follow_project_override(runner):
    print("\n[test] resolve_recipes: project-override roster => project recipe wins over LOCAL")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        # LOCAL roster (usable) + LOCAL recipes both exist in the Skill root.
        write(os.path.join(skill, "LOCAL_ROSTER.md"), usable_roster(agents=("LocalWorker",)))
        with open(os.path.join(skill, "LOCAL_INVOKE_RECIPES.json"), "w", encoding="utf-8") as f:
            json.dump({"recipes": {"r1": {"argv": ["x"], "probe_verified": True}},
                       "agent_recipes": {"LocalWorker": "r1"}}, f)
        # Project marks itself override and ships its OWN worker + recipes.
        write(os.path.join(inbox, "AGENT_ROSTER.md"),
              usable_roster(cal="CAL-3", agents=("ProjWorker",), override=True))
        with open(os.path.join(inbox, "invoke-recipes.json"), "w", encoding="utf-8") as f:
            json.dump({"recipes": {"pr": {"argv": ["p"], "probe_verified": True}},
                       "agent_recipes": {"ProjWorker": "pr"}}, f)
        # Import resolver directly for tight assertions (no CLI needed).
        import sys as _sys
        _sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
        os.environ["AFC_SKILL_ROOT"] = skill
        try:
            import importlib, afc_roster
            importlib.reload(afc_roster)
            path, source = afc_roster.resolve_recipes(inbox, roster_source="project-override")
            runner.check("project-override picks project recipe",
                         source == "project-override" and path == os.path.join(inbox, "invoke-recipes.json"),
                         "got source={} path={}".format(source, path))
            # When roster_source is install-local, LOCAL recipe wins.
            path2, source2 = afc_roster.resolve_recipes(inbox, roster_source="install-local")
            runner.check("install-local picks LOCAL recipe",
                         source2 == "install-local" and path2 == os.path.join(skill, "LOCAL_INVOKE_RECIPES.json"),
                         "got source={} path={}".format(source2, path2))
            # CAL-3 gate against marked project override + own recipe: usable.
            status = afc_roster.roster_status(inbox, require_cal3=True, agent_name="ProjWorker")
            runner.check("CAL-3 gate uses project recipe when roster is project-override",
                         status.get("roster_status") == "usable",
                         "status={}".format(status))
        finally:
            del os.environ["AFC_SKILL_ROOT"]
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_afc_init_template_does_not_shadow_local(runner):
    """A fresh afc-init inbox (unmarked TEMPLATE_ROSTER copy) must not shadow
    a usable install-local LOCAL_ROSTER.md."""
    print("\n[test] afc-init template does not shadow install-local roster")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        write(os.path.join(skill, "LOCAL_ROSTER.md"), usable_roster(agents=("LocalWorker",)))
        # Simulate afc-init.sh/ps1 copying TEMPLATE_ROSTER.md verbatim.
        tmpl_path = os.path.join(REPO_ROOT, "templates", "TEMPLATE_ROSTER.md")
        with open(tmpl_path, "r", encoding="utf-8") as f:
            tmpl = f.read()
        write(os.path.join(inbox, "AGENT_ROSTER.md"), tmpl)
        # Sanity: the resolver's marker detector must NOT treat the template as
        # a project-override (docstring inside a multi-line HTML comment).
        import sys as _sys
        _sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
        import importlib, afc_roster
        importlib.reload(afc_roster)
        runner.check(
            "template does not activate project-override",
            not afc_roster._has_project_override_marker(os.path.join(inbox, "AGENT_ROSTER.md")),
            "template top: {}".format(tmpl[:400]),
        )
        # Resolver must pick install-local, not the placeholder project roster.
        code, out, err = run_first_run(skill, inbox)
        s = parse_status(out)
        runner.check("resolver uses install-local", s.get("roster_source") == "install-local",
                     out[:400])
        runner.check("dispatch not blocked by placeholder project roster",
                     s.get("roster_status") == "usable", out[:400])
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_recipes_follow_legacy_fallback(runner):
    """resolve_recipes: project-legacy-fallback => project recipe wins over LOCAL_INVOKE_RECIPES.

    Symmetric to project-override: when the roster is being read from the
    project as a compatibility fallback, its own invoke-recipes.json must
    also take precedence over any install-local recipe file.
    """
    print("\n[test] resolve_recipes: legacy-fallback => project recipe wins over LOCAL")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        # Skill root has LOCAL_INVOKE_RECIPES.json but NO LOCAL_ROSTER.md.
        with open(os.path.join(skill, "LOCAL_INVOKE_RECIPES.json"), "w", encoding="utf-8") as f:
            json.dump({"recipes": {"r1": {"argv": ["x"], "probe_verified": True}},
                       "agent_recipes": {"LocalWorker": "r1"}}, f)
        # Project ships its own (unmarked) roster + its own recipes.
        write(os.path.join(inbox, "AGENT_ROSTER.md"),
              usable_roster(cal="CAL-3", agents=("LegacyWorker",)))
        with open(os.path.join(inbox, "invoke-recipes.json"), "w", encoding="utf-8") as f:
            json.dump({"recipes": {"lg": {"argv": ["p"], "probe_verified": True}},
                       "agent_recipes": {"LegacyWorker": "lg"}}, f)
        import sys as _sys
        _sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
        os.environ["AFC_SKILL_ROOT"] = skill
        try:
            import importlib, afc_roster
            importlib.reload(afc_roster)
            path, source = afc_roster.resolve_recipes(inbox, roster_source="project-legacy-fallback")
            runner.check("legacy-fallback picks project recipe",
                         source == "project-legacy" and path == os.path.join(inbox, "invoke-recipes.json"),
                         "got source={} path={}".format(source, path))
            # CAL-3 gate against a legacy-fallback roster + project recipe: usable + warning.
            status = afc_roster.roster_status(inbox, require_cal3=True, agent_name="LegacyWorker")
            runner.check("CAL-3 gate uses project recipe under legacy-fallback",
                         status.get("roster_status") == "usable",
                         "status={}".format(status))
            runner.check("legacy-fallback source recorded",
                         status.get("roster_source") == "project-legacy-fallback", status)
            runner.check("legacy-fallback warning emitted",
                         "legacy project AGENT_ROSTER.md" in (status.get("warning") or ""),
                         status.get("warning"))
        finally:
            del os.environ["AFC_SKILL_ROOT"]
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_write_target_follows_marked_override(runner):
    """--default-cal writes to the active project override, not LOCAL_ROSTER.md.

    When .agent-inbox/AGENT_ROSTER.md is marked project-override, the write
    target must be that file so the same roster the resolver picks receives
    the CAL default (Codex P2 review finding).
    """
    print("\n[test] --default-cal follows marked project-override")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        # Marked but SESSION-PREFERENCES-empty project override.
        write(os.path.join(inbox, "AGENT_ROSTER.md"),
              PROJECT_OVERRIDE_MARKER + "\n# Empty project override\n")
        cmd = [sys.executable, "-B", FIRST_RUN,
               "--inbox", inbox, "--skill-root", skill,
               "--default-cal", "CAL-2", "--confirmed-at", "2026-07-01"]
        env = dict(os.environ); env["AFC_SKILL_ROOT"] = skill
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        runner.check("write exit=0", r.returncode == 0,
                     "rc={} out={} err={}".format(r.returncode, r.stdout[:200], r.stderr[:200]))
        proj_roster = os.path.join(inbox, "AGENT_ROSTER.md")
        with open(proj_roster, "r", encoding="utf-8") as f:
            proj_text = f.read()
        runner.check("Default CAL written to project override",
                     "Default CAL: CAL-2" in proj_text, proj_text[:400])
        runner.check("marker survives",
                     PROJECT_OVERRIDE_MARKER in proj_text, proj_text[:400])
        runner.check("LOCAL_ROSTER.md not created",
                     not os.path.isfile(os.path.join(skill, "LOCAL_ROSTER.md")),
                     "skill contents: {}".format(os.listdir(skill)))
        # Follow-up --check-only against the same inbox reports CONFIGURED.
        r2 = subprocess.run([sys.executable, "-B", FIRST_RUN,
                             "--inbox", inbox, "--skill-root", skill, "--check-only"],
                            capture_output=True, text=True, timeout=30, env=env)
        runner.check("check-only sees CONFIGURED", r2.returncode == 0 and "CONFIGURED" in r2.stdout,
                     "rc={} out={}".format(r2.returncode, r2.stdout[:200]))
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_project_scoped_no_recipe_blocks_no_local_leak(runner):
    """CAL-3: project-scoped roster with no project invoke-recipes.json MUST
    NOT silently fall through to LOCAL_INVOKE_RECIPES.json even when that
    file has a probe-verified recipe for the same agent name (Codex P1)."""
    print("\n[test] project-scoped roster + no project recipe => CAL-3 blocks (no LOCAL leak)")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        # Skill root: LOCAL_INVOKE_RECIPES.json has a recipe for the same agent
        # name that appears in the project override. This is the exact leak
        # scenario Codex flagged.
        with open(os.path.join(skill, "LOCAL_INVOKE_RECIPES.json"), "w", encoding="utf-8") as f:
            json.dump({"recipes": {"loc": {"argv": ["l"], "probe_verified": True}},
                       "agent_recipes": {"CollWorker": "loc"}}, f)
        # Marked project override with CollWorker but NO project invoke-recipes.
        write(os.path.join(inbox, "AGENT_ROSTER.md"),
              usable_roster(cal="CAL-3", agents=("CollWorker",), override=True))
        import sys as _sys
        _sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
        os.environ["AFC_SKILL_ROOT"] = skill
        try:
            import importlib, afc_roster
            importlib.reload(afc_roster)
            # A. resolve_recipes for a project-scoped source returns missing.
            path, source = afc_roster.resolve_recipes(inbox, roster_source="project-override")
            runner.check("project-override without project recipe => missing",
                         path is None and source == "missing",
                         "got source={} path={}".format(source, path))
            # B. CAL-3 gate must block (no local leak).
            status = afc_roster.roster_status(inbox, require_cal3=True, agent_name="CollWorker")
            runner.check("CAL-3 gate blocks",
                         status.get("roster_status") != "usable",
                         "status={}".format(status))
            runner.check("cal3_callable_routes count is 0",
                         status.get("cal3_callable_routes", 0) == 0,
                         "status={}".format(status))
            # C. Symmetric legacy-fallback path also blocks with no local leak.
            proj2, inbox2 = make_proj_inbox()
            try:
                write(os.path.join(inbox2, "AGENT_ROSTER.md"),
                      usable_roster(cal="CAL-3", agents=("CollWorker",)))
                path2, source2 = afc_roster.resolve_recipes(inbox2, roster_source="project-legacy-fallback")
                runner.check("legacy-fallback without project recipe => missing",
                             path2 is None and source2 == "missing",
                             "got source={} path={}".format(source2, path2))
                status2 = afc_roster.roster_status(inbox2, require_cal3=True, agent_name="CollWorker")
                runner.check("legacy-fallback CAL-3 gate blocks",
                             status2.get("roster_status") != "usable",
                             "status={}".format(status2))
            finally:
                shutil.rmtree(proj2, True)
            # D. CAL-1/CAL-2 (require_cal3=False) is NOT affected by missing recipes.
            status_cal1 = afc_roster.roster_status(inbox, require_cal3=False, agent_name="CollWorker")
            runner.check("CAL-1/2 stays usable under project-override + no recipe",
                         status_cal1.get("roster_status") == "usable",
                         "status={}".format(status_cal1))
        finally:
            del os.environ["AFC_SKILL_ROOT"]
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_template_marker_activation_matrix(runner):
    """Template must not falsely activate marker; a correctly-written user
    marker must activate; a colon-less variant (the old buggy instruction)
    must not activate (Codex P2)."""
    print("\n[test] template marker activation matrix")
    import sys as _sys
    _sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
    import importlib, afc_roster
    importlib.reload(afc_roster)
    # A. Verbatim template copy must NOT activate.
    tmpl_path = os.path.join(REPO_ROOT, "templates", "TEMPLATE_ROSTER.md")
    with open(tmpl_path, "r", encoding="utf-8") as f: tmpl = f.read()
    proj, inbox = make_proj_inbox()
    try:
        p = os.path.join(inbox, "AGENT_ROSTER.md")
        write(p, tmpl)
        runner.check("template verbatim does not activate marker",
                     not afc_roster._has_project_override_marker(p),
                     "template top: {}".format(tmpl[:400]))
        # B. Correct marker on its own line DOES activate.
        write(p, PROJECT_OVERRIDE_MARKER + "\n" + tmpl)
        runner.check("correct single-line marker activates",
                     afc_roster._has_project_override_marker(p))
        # C. Colon-less variant does NOT activate.
        write(p, "<!-- AFC_ROSTER_SCOPE project-override -->\n" + tmpl)
        runner.check("colon-less variant does not activate",
                     not afc_roster._has_project_override_marker(p))
    finally:
        shutil.rmtree(proj, True)


def test_check_only_rejects_legacy_fallback(runner):
    """--check-only is a user-level onboarding question; a per-project
    legacy-fallback roster must NOT satisfy it (Codex P2). --roster-status
    (dispatch readiness) stays permissive for the same input."""
    print("\n[test] --check-only NOT_CONFIGURED under legacy-fallback; --roster-status still usable")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        # No LOCAL_ROSTER.md in the Skill root; unmarked project roster with CAL.
        write(os.path.join(inbox, "AGENT_ROSTER.md"),
              usable_roster(cal="CAL-1", agents=("LegacyWorker",)))
        env = dict(os.environ); env["AFC_SKILL_ROOT"] = skill
        # --check-only should refuse to accept the legacy fallback.
        r1 = subprocess.run(
            [sys.executable, "-B", FIRST_RUN, "--inbox", inbox,
             "--skill-root", skill, "--check-only"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        runner.check("--check-only exits 1 for legacy-fallback", r1.returncode == 1,
                     "rc={} out={!r}".format(r1.returncode, r1.stdout[:300]))
        runner.check("--check-only prints NOT_CONFIGURED", "NOT_CONFIGURED" in r1.stdout,
                     r1.stdout[:300])
        runner.check("--check-only reports legacy source",
                     "project-legacy-fallback" in r1.stdout, r1.stdout[:300])
        runner.check("--check-only returns ASK_CAL before routing",
                     "next_action: ASK_CAL" in r1.stdout, r1.stdout[:400])
        runner.check("--check-only nudges to write LOCAL_ROSTER.md",
                     "LOCAL_ROSTER.md" in r1.stdout, r1.stdout[:400])
        # --roster-status (dispatch readiness) MUST stay permissive; legacy
        # fallback is a valid dispatch source (with warning).
        r2 = subprocess.run(
            [sys.executable, "-B", FIRST_RUN, "--inbox", inbox,
             "--skill-root", skill, "--roster-status"],
            capture_output=True, text=True, timeout=30, env=env,
        )
        runner.check("--roster-status exits 0 for legacy-fallback (dispatch OK)",
                     r2.returncode == 0,
                     "rc={} out={!r}".format(r2.returncode, r2.stdout[:300]))
        runner.check("--roster-status reports usable", "roster_status: usable" in r2.stdout,
                     r2.stdout[:300])
        runner.check("--roster-status reports legacy source",
                     "project-legacy-fallback" in r2.stdout, r2.stdout[:300])
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def test_cal3_generic_gate_ignores_unrostered_recipe(runner):
    print("\n[test] generic CAL-3 gate ignores recipes for absent workers")
    skill = make_skill(); proj, inbox = make_proj_inbox()
    try:
        write(os.path.join(skill, "LOCAL_ROSTER.md"),
              usable_roster(cal="CAL-3", agents=("WorkerA",)))
        with open(os.path.join(skill, "LOCAL_INVOKE_RECIPES.json"), "w", encoding="utf-8") as handle:
            json.dump({"recipes": {"ghost": {"argv": ["ghost"], "probe_verified": True}},
                       "agent_recipes": {"GhostWorker": "ghost"}}, handle)
        os.environ["AFC_SKILL_ROOT"] = skill
        try:
            sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
            import importlib, afc_roster
            importlib.reload(afc_roster)
            status = afc_roster.roster_status(inbox, require_cal3=True)
            runner.check("unrostered recipe does not satisfy generic CAL-3 gate",
                         status.get("roster_status") != "usable" and
                         status.get("cal3_callable_routes") == 0,
                         "status={}".format(status))
        finally:
            del os.environ["AFC_SKILL_ROOT"]
    finally:
        shutil.rmtree(skill, True); shutil.rmtree(proj, True)


def main():
    runner = Runner()
    print("Running afc-roster-resolver tests...")
    for fn in [
        test_install_local_usable,
        test_no_local_no_project_missing,
        test_local_placeholder_no_fallback,
        test_local_shadows_unmarked_project,
        test_marked_project_override_usable,
        test_marked_project_override_incomplete_no_fallback,
        test_legacy_fallback_warning,
        test_explicit_roster_file,
        test_cal2_arm_install_local,
        test_recipes_follow_project_override,
        test_recipes_follow_legacy_fallback,
        test_project_scoped_no_recipe_blocks_no_local_leak,
        test_write_target_follows_marked_override,
        test_check_only_rejects_legacy_fallback,
        test_cal3_generic_gate_ignores_unrostered_recipe,
        test_afc_init_template_does_not_shadow_local,
        test_template_marker_activation_matrix,
    ]:
        fn(runner)
    return runner.report()


if __name__ == "__main__":
    sys.exit(main())
