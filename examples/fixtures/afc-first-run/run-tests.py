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


def run_script(*extra_args, timeout=30):
    """Run afc-first-run-config.py. Returns (exit_code, stdout, stderr)."""
    cmd = [sys.executable, "-B", SCRIPT] + list(extra_args)
    r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                       encoding="utf-8", errors="replace")
    return r.returncode, r.stdout, r.stderr


def make_fresh_inbox():
    """Create a temp project with .agent-inbox/ populated from template."""
    tmp = tempfile.mkdtemp(prefix="afc-first-run-")
    inbox = os.path.join(tmp, ".agent-inbox")
    os.makedirs(inbox)
    # Copy template roster
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        roster = f.read()
    with open(os.path.join(inbox, "AGENT_ROSTER.md"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(roster)
    # Create empty events.jsonl
    with open(os.path.join(inbox, "events.jsonl"), "w",
              encoding="utf-8", newline="\n") as f:
        pass
    return tmp, inbox


def cleanup(tmp):
    if tmp and os.path.isdir(tmp):
        shutil.rmtree(tmp, ignore_errors=True)


# --- Test cases ---------------------------------------------------------

def test_check_only_unconfigured(runner):
    """Fresh template: --check-only returns NOT_CONFIGURED (exit 1)."""
    print("\n[test] check-only on fresh template -> NOT_CONFIGURED")
    tmp, inbox = make_fresh_inbox()
    try:
        code, out, err = run_script("--inbox", inbox, "--check-only")
        runner.check("check-only exit=1 (unconfigured)", code == 1,
                     "exit={} stdout={!r} stderr={!r}".format(code, out[:200], err[:200]))
        runner.check("check-only prints NOT_CONFIGURED",
                     "NOT_CONFIGURED" in out,
                     "stdout={!r}".format(out[:200]))
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


def test_write_cal2(runner):
    """Write CAL-2 and preferences, then verify roster and event."""
    print("\n[test] write CAL-2 and preferences")
    tmp, inbox = make_fresh_inbox()
    try:
        code, out, err = run_script(
            "--inbox", inbox,
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
        runner.check("write prints OK", "OK" in out,
                     "stdout={!r}".format(out[:200]))

        # Verify roster content
        roster_path = os.path.join(inbox, "AGENT_ROSTER.md")
        with open(roster_path, "r", encoding="utf-8") as f:
            roster = f.read()
        runner.check("roster has Default CAL: CAL-2",
                     "Default CAL: CAL-2" in roster,
                     roster[:500])
        runner.check("roster has resources",
                     "Claude Code CLI, codex CLI" in roster,
                     roster[:500])
        runner.check("roster has available now",
                     "worker-cli, backup-cli" in roster,
                     roster[:500])
        runner.check("roster has model order",
                     "primary-model, review-model" in roster,
                     roster[:500])
        runner.check("roster has avoid",
                     "deprecated-model (unavailable)" in roster,
                     roster[:500])
        runner.check("roster has capability limits",
                     "no browser automation" in roster,
                     roster[:500])
        runner.check("roster has confirmed date",
                     "Confirmed: 2026-06-27" in roster,
                     roster[:500])

        # Verify event
        events_path = os.path.join(inbox, "events.jsonl")
        with open(events_path, "r", encoding="utf-8") as f:
            events_text = f.read()
        runner.check("events.jsonl has ROSTER_UPDATED",
                     "ROSTER_UPDATED" in events_text,
                     events_text[:300])
        runner.check("events.jsonl has CAL= in summary",
                     "CAL=CAL-2" in events_text or "CAL=CAL-2" in events_text.replace(" ", ""),
                     events_text[:300])
    finally:
        cleanup(tmp)


def test_check_only_configured(runner):
    """After writing, --check-only returns CONFIGURED (exit 0)."""
    print("\n[test] check-only after write -> CONFIGURED")
    tmp, inbox = make_fresh_inbox()
    try:
        # Write first
        run_script("--inbox", inbox, "--default-cal", "CAL-2",
                    "--confirmed-at", "2026-06-27")
        # Check
        code, out, err = run_script("--inbox", inbox, "--check-only")
        runner.check("check-only exit=0 (configured)", code == 0,
                     "exit={} stdout={!r}".format(code, out[:200]))
        runner.check("check-only prints CONFIGURED",
                     "CONFIGURED" in out,
                     "stdout={!r}".format(out[:200]))
        runner.check("check-only shows CAL-2",
                     "CAL-2" in out,
                     "stdout={!r}".format(out[:200]))
    finally:
        cleanup(tmp)


def test_events_append(runner):
    """Second write appends a second event (does not overwrite)."""
    print("\n[test] events.jsonl append (not overwrite)")
    tmp, inbox = make_fresh_inbox()
    try:
        run_script("--inbox", inbox, "--default-cal", "CAL-1",
                    "--confirmed-at", "2026-06-27")
        run_script("--inbox", inbox, "--default-cal", "CAL-2",
                    "--confirmed-at", "2026-06-28")
        events_path = os.path.join(inbox, "events.jsonl")
        with open(events_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        runner.check("events.jsonl has 2 lines", len(lines) == 2,
                     "lines={}".format(len(lines)))
        ids = set()
        for line in lines:
            evt = json.loads(line)
            ids.add(evt.get("event_id"))
        runner.check("event IDs are distinct", len(ids) == 2,
                     "ids={}".format(ids))
    finally:
        cleanup(tmp)


def test_invalid_cal_rejected(runner):
    """Invalid CAL value is rejected with exit 1."""
    print("\n[test] invalid CAL rejected")
    tmp, inbox = make_fresh_inbox()
    try:
        code, out, err = run_script(
            "--inbox", inbox, "--default-cal", "CAL-99",
            "--confirmed-at", "2026-06-27",
        )
        # argparse rejects invalid choice before main runs
        runner.check("invalid CAL exit != 0", code != 0,
                     "exit={} stdout={!r} stderr={!r}".format(code, out[:200], err[:200]))
    finally:
        cleanup(tmp)


def test_secret_rejected(runner):
    """Secret-looking input is rejected with exit 1."""
    print("\n[test] secret input rejected")
    tmp, inbox = make_fresh_inbox()
    try:
        code, out, err = run_script(
            "--inbox", inbox, "--default-cal", "CAL-2",
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


def test_preserve_existing_table(runner):
    """Existing roster table rows are preserved after write."""
    print("\n[test] existing roster table preserved")
    tmp, inbox = make_fresh_inbox()
    try:
        # Add a custom row to the roster before writing config
        roster_path = os.path.join(inbox, "AGENT_ROSTER.md")
        with open(roster_path, "r", encoding="utf-8") as f:
            roster = f.read()
        custom_row = ("| MyCustomAgent | implementer | custom | GPT-4o "
                      "| local | task-only | no | yes | yes | unknown "
                      "| unknown | custom work | n/a | added by test |")
        roster = roster + "\n" + custom_row + "\n"
        with open(roster_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(roster)
        # Write config
        run_script("--inbox", inbox, "--default-cal", "CAL-1",
                    "--confirmed-at", "2026-06-27")
        # Verify custom row still present
        with open(roster_path, "r", encoding="utf-8") as f:
            after = f.read()
        runner.check("custom row preserved",
                     "MyCustomAgent" in after,
                     after[:800])
        runner.check("CAL written",
                     "Default CAL: CAL-1" in after,
                     after[:800])
    finally:
        cleanup(tmp)


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
    try:
        code, out, err = run_script(
            "--inbox", inbox, "--default-cal", "CAL-2",
            "--confirmed-at", "not-a-date",
        )
        runner.check("invalid date exit=1", code == 1,
                     "exit={} stderr={!r}".format(code, err[:200]))
    finally:
        cleanup(tmp)


def test_non_dict_events_no_crash(runner):
    """P1 regression: non-dict JSON lines in events.jsonl must not crash."""
    print("\n[test] non-dict JSON in events.jsonl (P1 regression)")
    tmp, inbox = make_fresh_inbox()
    try:
        # Seed events.jsonl with a non-dict JSON line
        events_path = os.path.join(inbox, "events.jsonl")
        with open(events_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("[]\n")
        code, out, err = run_script(
            "--inbox", inbox, "--default-cal", "CAL-1",
            "--confirmed-at", "2026-06-27",
        )
        runner.check("write with [] in events.jsonl exit=0", code == 0,
                     "exit={} stdout={!r} stderr={!r}".format(code, out[:200], err[:200]))
        # Verify event was appended (not replacing the [])
        with open(events_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        runner.check("events.jsonl has 2 lines (skip [] + new event)",
                     len(lines) == 2,
                     "lines={}".format(len(lines)))
        evt = json.loads(lines[1])
        runner.check("appended event is ROSTER_UPDATED",
                     evt.get("event_type") == "ROSTER_UPDATED",
                     "evt={}".format(evt))
        runner.check("appended event_id is evt-001 (skipped non-dict)",
                     evt.get("event_id") == "evt-001",
                     "evt_id={}".format(evt.get("event_id")))
    finally:
        cleanup(tmp)


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
    test_print_questionnaire(runner)
    test_write_cal2(runner)
    test_check_only_configured(runner)
    test_events_append(runner)
    test_invalid_cal_rejected(runner)
    test_secret_rejected(runner)
    test_preserve_existing_table(runner)
    test_recommend_cal1(runner)
    test_recommend_cal3(runner)
    test_recommend_cal2_auto_intake(runner)
    test_recommend_substring_trap(runner)
    test_recommend_cal3_priority(runner)
    test_invalid_date_rejected(runner)
    test_non_dict_events_no_crash(runner)

    return runner.report()


if __name__ == "__main__":
    sys.exit(main())
