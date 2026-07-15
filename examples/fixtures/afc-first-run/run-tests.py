#!/usr/bin/env python3
"""Test runner for afc-first-run-config.py.

Python stdlib only. Exercises check-only, questionnaire output, write,
re-check, event append, invalid CAL rejection, secret rejection, and
roster-table preservation.

Usage:
    python -B examples/fixtures/afc-first-run/run-tests.py

Exit codes:
    0   all tests passed
    1   at least one test failed
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:
    pass

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "afc-first-run-config.py")
ROUTE = os.path.join(REPO_ROOT, "scripts", "afc-route.py")
TEMPLATE = os.path.join(REPO_ROOT, "templates", "TEMPLATE_ROSTER.md")


# --- Test runner --------------------------------------------------------

class Runner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.failures = []

    def check(self, name, ok, detail=""):
        if ok:
            self.passed += 1
            print("  [PASS] {}".format(name))
        else:
            self.failed += 1
            self.failures.append((name, detail))
            print("  [FAIL] {}: {}".format(name, detail[:300]))

    def skip(self, name, reason):
        self.skipped += 1
        print("  [SKIP] {}: {}".format(name, reason))

    def report(self):
        print()
        print("=" * 60)
        print("passed: {}".format(self.passed))
        print("failed: {}".format(self.failed))
        print("skipped: {}".format(self.skipped))
        if self.failures:
            print("failures:")
            for name, detail in self.failures:
                print("  - {}: {}".format(name, detail[:200]))
        return 0 if self.failed == 0 else 1


def run_script(*extra_args, skill=None, timeout=30):
    """Run afc-first-run-config.py. If skill is given, set AFC_SKILL_ROOT to it
    (so writes/reads target the install-local LOCAL_ROSTER.md in that temp)."""
    cmd = [sys.executable, "-B", SCRIPT] + list(extra_args)
    env = dict(os.environ)
    if skill is not None:
        env["AFC_SKILL_ROOT"] = skill
    else:
        env.pop("AFC_SKILL_ROOT", None)
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def run_route(*extra_args, cwd=None, timeout=30):
    cmd = [sys.executable, "-B", ROUTE] + list(extra_args)
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def make_fresh_inbox():
    """Create a temp project with .agent-inbox/ but NO AGENT_ROSTER.md.

    Roster resolution now defaults to the install-local LOCAL_ROSTER.md
    (selected via --skill-root). Tests that need a legacy project roster
    write it explicitly via write_user_relay_roster()."""
    tmp = tempfile.mkdtemp(prefix="afc-first-run-")
    inbox = os.path.join(tmp, ".agent-inbox")
    os.makedirs(inbox)
    # Create empty events.jsonl
    with open(os.path.join(inbox, "events.jsonl"), "w",
              encoding="utf-8", newline="\n") as f:
        pass
    return tmp, inbox


def cleanup(tmp):
    if tmp and os.path.isdir(tmp):
        shutil.rmtree(tmp, ignore_errors=True)


def make_skill():
    """Create a temp skill root for the install-local LOCAL_ROSTER.md."""
    return tempfile.mkdtemp(prefix="afc-skill-root-")


def write_user_relay_roster(inbox, default_cal="CAL-3"):
    with open(os.path.join(inbox, "AGENT_ROSTER.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("""---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---
# Agent Roster

<!-- SESSION PREFERENCES
Default CAL: {default_cal}
Execution preference: fixture user relay
Available resources: external user-relay worker
Available now: RelayWorker
Model preference order: fixture model
Avoid / unavailable: none
Smoke tests: fixture
Confirmed: 2026-06-29
Change policy: keep these defaults until the user asks to change them or a route becomes unavailable.
-->

| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Coordinator | coordinator | codex | coordinator-model | local coordinator | full-skill | yes | yes | bounded | yes | yes | can_use_existing | task decomposition, evidence review, final verdict | routine worker loops | fixture coordinator |
| RelayWorker | implementer | external-chat | user-relay-model | user-relay:RelayWorker | task-only | no | yes | tests_only | yes | no | manual_needed | fixture work | none | external user-relay worker |
""".format(default_cal=default_cal))


# --- Test cases ---------------------------------------------------------

def test_check_only_unconfigured(runner):
    """Fresh template: --check-only returns NOT_CONFIGURED (exit 1)."""
    print("\n[test] check-only on fresh template -> NOT_CONFIGURED")
    tmp, inbox = make_fresh_inbox()
    skill = make_skill()
    try:
        code, out, err = run_script("--inbox", inbox, "--skill-root", skill, "--check-only")
        runner.check("check-only exit=1 (unconfigured)", code == 1,
                     "exit={} stdout={!r} stderr={!r}".format(code, out[:200], err[:200]))
        runner.check("check-only prints NOT_CONFIGURED",
                     "NOT_CONFIGURED" in out,
                     "stdout={!r}".format(out[:200]))
        runner.check("check-only returns ASK_CAL before routing",
                     "next_action: ASK_CAL" in out,
                     "stdout={!r}".format(out[:300]))
    finally:
        cleanup(tmp)
        cleanup(skill)


def test_direct_route_missing_roster_stays_light(runner):
    """DIRECT routing must not require a roster or create coordination files."""
    print("\n[test] DIRECT route stays light with missing roster")
    tmp = tempfile.mkdtemp(prefix="afc-route-direct-")
    try:
        code, out, err = run_route(
            "--estimated-direct-minutes", "5",
            "--independent-workstreams", "1",
            "--smallest-workstream-minutes", "5",
            "--specialized-capability", "no",
            "--high-risk-independent-review", "no",
            "--external-worker-required", "no",
            "--semantic-change", "no",
            "--expected-rounds", "1",
            "--context-bytes", "100",
            cwd=tmp,
        )
        runner.check("route exit=0", code == 0,
                     "exit={} stdout={!r} stderr={!r}".format(code, out[:200], err[:200]))
        runner.check("route decision DIRECT", "DIRECT" in out,
                     "stdout={!r}".format(out[:300]))
        runner.check("no inbox created", not os.path.exists(os.path.join(tmp, ".agent-inbox")),
                     "entries={}".format(os.listdir(tmp)))
    finally:
        cleanup(tmp)


def test_print_questionnaire(runner):
    """--print-questionnaire outputs the standard questions."""
    print("\n[test] print-questionnaire")
    code, out, err = run_script("--print-questionnaire")
    runner.check("questionnaire exit=0", code == 0,
                 "exit={} stderr={!r}".format(code, err[:200]))
    runner.check("questionnaire has Session Bootstrap",
                 "Session Bootstrap" in out, "stdout={!r}".format(out[:200]))
    runner.check("questionnaire has CAL preference",
                 "CAL preference" in out, "stdout={!r}".format(out[:200]))
    runner.check("questionnaire has Model preference order",
                 "Model preference order" in out, "stdout={!r}".format(out[:200]))
    runner.check("questionnaire names cross-project shared default",
                 "shared across projects" in out,
                 "stdout={!r}".format(out[:400]))
    runner.check("questionnaire avoids misleading project-local wording",
                 "this project's default" not in out.lower(),
                 "stdout={!r}".format(out[:400]))


def test_write_cal2(runner):
    """Write CAL-2 to the install-local LOCAL_ROSTER.md and verify it."""
    print("\n[test] write CAL-2 to LOCAL_ROSTER.md")
    tmp, inbox = make_fresh_inbox()
    skill = make_skill()
    try:
        code, out, err = run_script(
            "--inbox", inbox, "--skill-root", skill,
            "--default-cal", "CAL-2",
            "--resources", "Claude Code CLI, codex CLI",
            "--available-now", "worker-cli, backup-cli",
            "--model-order", "primary-model, review-model",
            "--avoid", "deprecated-model (unavailable)",
            "--capability-limits", "no browser automation",
            "--confirmed-at", "2026-06-27",
        )
        runner.check("write exit=0", code == 0,
                     "exit={} stdout={!r} stderr={!r}".format(code, out[:300], err[:200]))
        runner.check("write prints OK", "OK" in out, "stdout={!r}".format(out[:200]))
        roster_path = os.path.join(skill, "LOCAL_ROSTER.md")
        runner.check("LOCAL_ROSTER.md created", os.path.isfile(roster_path),
                     "skill dir={}".format(os.listdir(skill)))
        with open(roster_path, "r", encoding="utf-8") as f:
            roster = f.read()
        runner.check("Default CAL: CAL-2", "Default CAL: CAL-2" in roster, roster[:500])
        runner.check("resources recorded", "Claude Code CLI, codex CLI" in roster, roster[:500])
        runner.check("available now recorded", "worker-cli, backup-cli" in roster, roster[:500])
        runner.check("model order recorded", "primary-model, review-model" in roster, roster[:500])
        runner.check("avoid recorded", "deprecated-model (unavailable)" in roster, roster[:500])
        runner.check("capability limits recorded", "no browser automation" in roster, roster[:500])
        runner.check("confirmed date", "Confirmed: 2026-06-27" in roster, roster[:500])
        # Global roster update must not write a project events.jsonl entry.
        with open(os.path.join(inbox, "events.jsonl"), "r", encoding="utf-8") as f:
            events_text = f.read()
        runner.check("no ROSTER_UPDATED event for global write",
                     "ROSTER_UPDATED" not in events_text, events_text[:200])
    finally:
        cleanup(tmp)
        cleanup(skill)


def test_check_only_configured(runner):
    """After writing LOCAL_ROSTER.md, --check-only returns CONFIGURED."""
    print("\n[test] check-only after write -> CONFIGURED")
    tmp, inbox = make_fresh_inbox()
    skill = make_skill()
    try:
        run_script("--inbox", inbox, "--skill-root", skill,
                   "--default-cal", "CAL-2", "--confirmed-at", "2026-06-27")
        code, out, err = run_script("--inbox", inbox, "--skill-root", skill, "--check-only")
        runner.check("check-only exit=0 (configured)", code == 0,
                     "exit={} stdout={!r}".format(code, out[:200]))
        runner.check("check-only prints CONFIGURED", "CONFIGURED" in out,
                     "stdout={!r}".format(out[:200]))
        runner.check("check-only shows CAL-2", "CAL-2" in out,
                     "stdout={!r}".format(out[:200]))
        runner.check("check-only source install-local", "install-local" in out,
                     "stdout={!r}".format(out[:200]))
    finally:
        cleanup(tmp)
        cleanup(skill)


def test_roster_status_requested_mode(runner):
    """Default CAL-3 must not block explicit user-relay roster status checks."""
    print("\n[test] roster-status respects requested dispatch mode")
    tmp, inbox = make_fresh_inbox()
    skill = make_skill()
    try:
        write_user_relay_roster(inbox, default_cal="CAL-3")
        code, out, err = run_script(
            "--inbox", inbox, "--skill-root", skill, "--roster-status", "--dispatch-mode", "lite"
        )
        runner.check("lite roster-status exit=0", code == 0,
                     "exit={} stdout={!r} stderr={!r}".format(code, out[:300], err[:200]))
        runner.check("lite roster-status usable", "roster_status: usable" in out,
                     "stdout={!r}".format(out[:300]))
        code, out, err = run_script(
            "--inbox", inbox, "--skill-root", skill, "--roster-status", "--dispatch-mode", "cal-3"
        )
        runner.check("cal-3 roster-status exit=1 without probe", code == 1,
                     "exit={} stdout={!r} stderr={!r}".format(code, out[:300], err[:200]))
        runner.check("cal-3 roster-status requires probe", "CAL-3 requires" in out,
                     "stdout={!r}".format(out[:300]))
    finally:
        cleanup(tmp)
        cleanup(skill)


def test_roster_status_no_local_roster(runner):
    """No install-local LOCAL_ROSTER.md and no usable project roster => missing."""
    print("\n[test] no LOCAL + no usable project roster => missing")
    tmp, inbox = make_fresh_inbox()
    skill = make_skill()
    try:
        code, out, err = run_script("--inbox", inbox, "--skill-root", skill, "--roster-status")
        runner.check("exit=1", code == 1, "exit={} out={!r}".format(code, out[:300]))
        runner.check("status missing", "roster_status: missing" in out, out[:300])
        runner.check("configure_local_roster", "configure_local_roster" in out, out[:300])
    finally:
        cleanup(tmp)
        cleanup(skill)


def test_invalid_cal_rejected(runner):
    """Invalid CAL value is rejected with exit 1."""
    print("\n[test] invalid CAL rejected")
    tmp, inbox = make_fresh_inbox()
    skill = make_skill()
    try:
        code, out, err = run_script(
            "--inbox", inbox, "--skill-root", skill, "--default-cal", "CAL-99",
            "--confirmed-at", "2026-06-27",
        )
        # argparse rejects invalid choice before main runs
        runner.check("invalid CAL exit != 0", code != 0,
                     "exit={} stdout={!r} stderr={!r}".format(code, out[:200], err[:200]))
    finally:
        cleanup(tmp)
        cleanup(skill)


def test_secret_rejected(runner):
    """Secret-looking input is rejected with exit 1."""
    print("\n[test] secret input rejected")
    tmp, inbox = make_fresh_inbox()
    skill = make_skill()
    try:
        code, out, err = run_script(
            "--inbox", inbox, "--skill-root", skill, "--default-cal", "CAL-2",
            "--resources", "api_key=FAKE_SECRET_TOKEN_FOR_TEST_12345",
            "--confirmed-at", "2026-06-27",
        )
        runner.check("secret input exit=1", code == 1,
                     "exit={} stdout={!r} stderr={!r}".format(code, out[:200], err[:200]))
        runner.check("secret error mentions secret",
                     "secret" in err.lower(),
                     "stderr={!r}".format(err[:300]))
    finally:
        cleanup(tmp)
        cleanup(skill)


def test_recommend_cal1(runner):
    """No CLI indicators -> recommends CAL-1."""
    print("\n[test] recommend CAL-1")
    code, out, err = run_script("--recommend", "--resources", "chat only",
                                "--available-now", "manual worker")
    runner.check("recommend exit=0", code == 0,
                 "exit={} stderr={!r}".format(code, err[:200]))
    runner.check("recommends CAL-1", "CAL-1" in out,
                 "stdout={!r}".format(out[:200]))


def test_recommend_cal3(runner):
    """CLI indicators -> recommends CAL-3."""
    print("\n[test] recommend CAL-3")
    code, out, err = run_script("--recommend", "--resources", "claudecode CLI",
                                "--available-now", "headless dispatch ready")
    runner.check("recommend exit=0", code == 0,
                 "exit={} stderr={!r}".format(code, err[:200]))
    runner.check("recommends CAL-3", "CAL-3" in out,
                 "stdout={!r}".format(out[:200]))


def test_invalid_date_rejected(runner):
    """Invalid confirmed-at date is rejected."""
    print("\n[test] invalid date rejected")
    tmp, inbox = make_fresh_inbox()
    skill = make_skill()
    try:
        code, out, err = run_script(
            "--inbox", inbox, "--skill-root", skill, "--default-cal", "CAL-2",
            "--confirmed-at", "not-a-date",
        )
        runner.check("invalid date exit=1", code == 1,
                     "exit={} stderr={!r}".format(code, err[:200]))
    finally:
        cleanup(tmp)
        cleanup(skill)


def test_recommend_cal2_auto_intake(runner):
    """P2 regression: 'auto intake' must recommend CAL-2, not CAL-3."""
    print("\n[test] recommend CAL-2 for auto intake (P2 regression)")
    code, out, err = run_script("--recommend",
                                "--resources", "foreground watcher",
                                "--available-now", "CAL-2 auto intake")
    runner.check("recommend exit=0", code == 0,
                 "exit={} stderr={!r}".format(code, err[:200]))
    runner.check("recommends CAL-2 (not CAL-3)", "CAL-2" in out and "CAL-3" not in out,
                 "stdout={!r}".format(out[:200]))


def test_recommend_substring_trap(runner):
    """Word-boundary matching: 'cli' inside 'client' must not trigger CAL-3."""
    print("\n[test] recommend substring trap ('client' is not 'cli')")
    code, out, err = run_script("--recommend",
                                "--resources", "client portal access",
                                "--available-now", "chat only, manual relay")
    runner.check("recommend exit=0", code == 0,
                 "exit={} stderr={!r}".format(code, err[:200]))
    runner.check("recommends CAL-1 (no whole-word indicator)",
                 "CAL-1" in out and "CAL-3" not in out,
                 "stdout={!r}".format(out[:200]))


def test_recommend_cal3_priority(runner):
    """When both CLI and watcher indicators appear, CAL-2 wins over CAL-3."""
    print("\n[test] recommend CAL-2 wins when watcher + CLI both present")
    code, out, err = run_script("--recommend",
                                "--resources", "claude CLI with foreground watcher",
                                "--available-now", "auto intake")
    runner.check("recommend exit=0", code == 0,
                 "exit={} stderr={!r}".format(code, err[:200]))
    runner.check("recommends CAL-2 (watcher outranks CLI)",
                 "CAL-2" in out and "CAL-3" not in out,
                 "stdout={!r}".format(out[:200]))


# --- Main ---------------------------------------------------------------

def main():
    runner = Runner()
    print("Running afc-first-run-config tests...")

    test_check_only_unconfigured(runner)
    test_direct_route_missing_roster_stays_light(runner)
    test_print_questionnaire(runner)
    test_write_cal2(runner)
    test_check_only_configured(runner)
    test_roster_status_requested_mode(runner)
    test_roster_status_no_local_roster(runner)
    test_invalid_cal_rejected(runner)
    test_secret_rejected(runner)
    test_recommend_cal1(runner)
    test_recommend_cal3(runner)
    test_recommend_cal2_auto_intake(runner)
    test_recommend_substring_trap(runner)
    test_recommend_cal3_priority(runner)
    test_invalid_date_rejected(runner)

    return runner.report()


if __name__ == "__main__":
    sys.exit(main())
