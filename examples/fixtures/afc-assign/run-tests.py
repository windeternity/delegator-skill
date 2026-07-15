#!/usr/bin/env python3
"""Fixture runner for afc-assign.py.

Exercises success and failure cases, then validates generated artifacts
with the project validator. Returns exit 0 when all checks pass.
"""

import json
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import threading

SCRIPT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "afc-assign.py"))
VALIDATOR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "validate-agent-inbox.py"))
AFC_STATUS = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "afc-status.py"))
FIXTURES = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_ROSTER = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "templates", "TEMPLATE_ROSTER.md"))

PASS = 0
FAIL = 0
_SHARED_TEMP = None  # set in main(), used by all tests for generated output


def _temp_inbox(name):
    """Create and return a temp subdirectory under _SHARED_TEMP for a test."""
    path = os.path.join(_SHARED_TEMP, name)
    os.makedirs(path, exist_ok=True)
    write_usable_roster(path)
    return path


def write_usable_roster(inbox, agents=None, default_cal="CAL-1"):
    if agents is None:
        agents = [
            "DocsWorker",
            "TestWorker",
            "ReleaseBot",
            "SeqWorker",
            "ExistingWorker",
        ]
    rows = []
    for agent in agents:
        rows.append(
            "| {agent} | implementer | external-chat | user-relay-model | user-relay:{agent} | task-only | no | yes | tests_only | yes | no | manual_needed | fixture work | none | external user-relay worker |".format(
                agent=agent
            )
        )
    text = """---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---

# Agent Roster

<!-- SESSION PREFERENCES
Default CAL: {default_cal}
Execution preference: fixture external workers
Available resources: external user-relay workers
Available now: {agents}
Model preference order: fixture model
Avoid / unavailable: none
Smoke tests: fixture
Confirmed: 2026-06-29
Change policy: keep these defaults until the user asks to change them or a route becomes unavailable.
-->

| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Coordinator | coordinator | codex | coordinator-model | local coordinator | full-skill | yes | yes | bounded | yes | yes | can_use_existing | task decomposition, evidence review, final verdict | routine worker loops | fixture coordinator |
{rows}
""".format(default_cal=default_cal, agents=", ".join(agents), rows="\n".join(rows))
    with open(os.path.join(inbox, "AGENT_ROSTER.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def write_internal_route_roster(inbox, agent="DocsWorker", tool="current-session subagent"):
    text = """---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---

# Agent Roster

<!-- SESSION PREFERENCES
Default CAL: CAL-1
Execution preference: invalid internal route fixture
Available resources: {tool}
Available now: {agent}
Model preference order: fixture model
Avoid / unavailable: none
Smoke tests: fixture
Confirmed: 2026-06-29
Change policy: keep these defaults until the user asks to change them or a route becomes unavailable.
-->

| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Coordinator | coordinator | codex | coordinator-model | local coordinator | full-skill | yes | yes | bounded | yes | yes | can_use_existing | task decomposition, evidence review, final verdict | routine worker loops | fixture coordinator |
| {agent} | implementer | {tool} | helper-model | coordinator runtime | task-only | no | yes | tests_only | yes | no | manual_needed | fixture work | none | built-in helper inside coordinator runtime |
""".format(agent=agent, tool=tool)
    with open(os.path.join(inbox, "AGENT_ROSTER.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def run(label, cmd, expect_exit=0, env=None):
    global PASS, FAIL
    if (
        SCRIPT in cmd
        and "--spec" in cmd
        and "--legacy-unrouted" not in cmd
    ):
        cmd = list(cmd) + ["--legacy-unrouted"]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    ok = (r.returncode == expect_exit)
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {label} (exit={r.returncode}, expected={expect_exit})")
    if not ok:
        FAIL += 1
        print(f"    stdout: {r.stdout[:500]}")
        print(f"    stderr: {r.stderr[:500]}")
    else:
        PASS += 1
    return r


def non_roster_files(inbox):
    return sorted(name for name in os.listdir(inbox) if name != "AGENT_ROSTER.md")


def test_valid_generates_valid_task():
    """Valid spec produces a task file that passes the validator."""
    global PASS, FAIL
    inbox = _temp_inbox("valid")
    spec = os.path.join(FIXTURES, "valid", "spec.yaml")
    r = run("valid: generate", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-08"])
    if r.returncode != 0:
        return

    # Validate the generated task file
    task_file = os.path.join(inbox, "task-DocsWorker-fix-readme-typo.md")
    if os.path.exists(task_file):
        run("valid: task passes validator", [sys.executable, "-B", VALIDATOR, task_file])
        # Check status is ASSIGNED, not DRAFT
        with open(task_file) as f:
            content = f.read()
        if "status: ASSIGNED" in content:
            pass  # ok
        else:
            FAIL += 1
            print("  [FAIL] valid: task status is not ASSIGNED")
    else:
        FAIL += 1
        print("  [FAIL] valid: task file not created")

    # Validate events.jsonl
    events_file = os.path.join(inbox, "events.jsonl")
    if os.path.exists(events_file):
        run("valid: events.jsonl passes validator", [sys.executable, "-B", VALIDATOR, events_file])
        # Check event content
        with open(events_file) as f:
            line = f.readline()
        evt = json.loads(line)
        if evt.get("event_type") == "TASK_ASSIGNED" and evt.get("task_id") == "fix-readme-typo":
            if evt.get("status") == "ASSIGNED":
                pass  # ok
            else:
                FAIL += 1
                print(f"  [FAIL] valid: event status is {evt.get('status')!r}, expected ASSIGNED")
        else:
            FAIL += 1
            print("  [FAIL] valid: event missing TASK_ASSIGNED or wrong task_id")
    else:
        FAIL += 1
        print("  [FAIL] valid: events.jsonl not created")

    # Check handoff contains key lines
    if "You are DocsWorker." in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] valid: handoff missing 'You are DocsWorker.'")
    if "Do not commit or push." in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] valid: handoff missing 'Do not commit or push.'")
    # Check handoff references actual inbox path, not generic text
    if "Do not open" in r.stdout and "as the project" in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] valid: handoff missing inbox path gate")


def test_roster_missing_blocks_full_assignment():
    """FULL task generation blocks before writing files when roster is missing."""
    global PASS, FAIL
    inbox = os.path.join(_SHARED_TEMP, "roster-missing")
    os.makedirs(inbox, exist_ok=True)
    spec = os.path.join(FIXTURES, "valid", "spec.yaml")
    r = run("roster-missing: blocks full assignment", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-29"], expect_exit=1)
    if "ROSTER_BLOCKED" not in r.stderr or "missing" not in r.stderr:
        FAIL += 1
        print("  [FAIL] roster-missing: stderr missing roster block")
    if os.listdir(inbox):
        FAIL += 1
        print("  [FAIL] roster-missing: files were written: {}".format(os.listdir(inbox)))


def test_roster_placeholder_blocks_full_assignment():
    """Template-only roster is not usable for FULL task generation."""
    global PASS, FAIL
    inbox = os.path.join(_SHARED_TEMP, "roster-placeholder")
    os.makedirs(inbox, exist_ok=True)
    with open(TEMPLATE_ROSTER, encoding="utf-8") as f:
        template = f.read()
    with open(os.path.join(inbox, "AGENT_ROSTER.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(template)
    spec = os.path.join(FIXTURES, "valid", "spec.yaml")
    r = run("roster-placeholder: blocks full assignment", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-29"], expect_exit=1)
    if "placeholder_only" not in r.stderr:
        FAIL += 1
        print("  [FAIL] roster-placeholder: stderr missing placeholder_only")
    if non_roster_files(inbox):
        FAIL += 1
        print("  [FAIL] roster-placeholder: task artifacts were written: {}".format(non_roster_files(inbox)))


def test_roster_incomplete_blocks_full_assignment():
    """Roster with CAL but no worker route is incomplete."""
    global PASS, FAIL
    inbox = os.path.join(_SHARED_TEMP, "roster-incomplete")
    os.makedirs(inbox, exist_ok=True)
    write_usable_roster(inbox, agents=[])
    spec = os.path.join(FIXTURES, "valid", "spec.yaml")
    r = run("roster-incomplete: blocks full assignment", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-29"], expect_exit=1)
    if "incomplete" not in r.stderr or "usable external" not in r.stderr:
        FAIL += 1
        print("  [FAIL] roster-incomplete: stderr missing incomplete reason")
    if non_roster_files(inbox):
        FAIL += 1
        print("  [FAIL] roster-incomplete: task artifacts were written: {}".format(non_roster_files(inbox)))


def test_unmatched_worker_alias_blocks_no_subagent_fallback():
    """A worker missing from the roster must not fall back to a current-session helper."""
    global PASS, FAIL
    inbox = os.path.join(_SHARED_TEMP, "roster-unmatched")
    os.makedirs(inbox, exist_ok=True)
    write_usable_roster(inbox, agents=["OtherWorker"])
    spec = os.path.join(FIXTURES, "valid", "spec.yaml")
    r = run("roster-unmatched: blocks full assignment", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-29"], expect_exit=1)
    if "DocsWorker" not in r.stderr or "not a usable external roster route" not in r.stderr:
        FAIL += 1
        print("  [FAIL] roster-unmatched: stderr missing unmatched worker reason")
    if non_roster_files(inbox):
        FAIL += 1
        print("  [FAIL] roster-unmatched: task artifacts were written: {}".format(non_roster_files(inbox)))


def test_matched_internal_worker_route_blocks_no_artifacts():
    """A matching roster row that points to a current-session subagent is invalid."""
    global PASS, FAIL
    inbox = os.path.join(_SHARED_TEMP, "roster-internal-route")
    os.makedirs(inbox, exist_ok=True)
    write_internal_route_roster(inbox, agent="DocsWorker")
    spec = os.path.join(FIXTURES, "valid", "spec.yaml")
    r = run("roster-internal-route: blocks full assignment", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-29"], expect_exit=1)
    if "ROSTER_BLOCKED" not in r.stderr or "current-session subagent" not in r.stderr:
        FAIL += 1
        print("  [FAIL] roster-internal-route: stderr missing internal route block")
    if non_roster_files(inbox):
        FAIL += 1
        print("  [FAIL] roster-internal-route: task artifacts were written: {}".format(non_roster_files(inbox)))


def test_builtin_subagent_alias_blocks_no_artifacts():
    inbox = os.path.join(_SHARED_TEMP, "roster-builtin-subagent-route")
    os.makedirs(inbox, exist_ok=True)
    spec = os.path.join(FIXTURES, "valid", "spec.yaml")
    write_internal_route_roster(inbox, agent="DocsWorker", tool="built-in subagent")
    r = run("roster-builtin-subagent-route: blocks full assignment", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-29"], expect_exit=1)
    if "ROSTER_BLOCKED" not in r.stderr:
        raise AssertionError(r.stderr)
    if non_roster_files(inbox):
        raise AssertionError("internal route wrote artifacts: {}".format(non_roster_files(inbox)))


def test_status_semantics():
    """Generated task shows ASSIGNED/wait_for_report via afc-status dry-run."""
    global PASS, FAIL
    inbox = os.path.join(_SHARED_TEMP, "valid")  # reuse valid test output
    if not os.path.isdir(inbox):
        FAIL += 1
        print("  [SKIP] status-semantics: valid temp dir not available (run valid test first)")
        return

    r = run("status-semantics: afc-status dry-run",
            [sys.executable, "-B", AFC_STATUS, "--dry-run", "--updated-at", "2026-06-08", inbox])
    if r.returncode != 0:
        return

    # Should show ASSIGNED and wait_for_report
    if "ASSIGNED" in r.stdout and "wait_for_report" in r.stdout:
        pass  # ok
    else:
        FAIL += 1
        print(f"  [FAIL] status-semantics: expected ASSIGNED/wait_for_report in output:\n{r.stdout[:500]}")
    # Should NOT show DRAFT or assign_worker
    if "DRAFT" in r.stdout:
        FAIL += 1
        print("  [FAIL] status-semantics: DRAFT found in afc-status output")
    if "assign_worker" in r.stdout:
        FAIL += 1
        print("  [FAIL] status-semantics: assign_worker found in afc-status output")


def test_dry_run_no_files():
    """Dry-run prints task but writes nothing."""
    global PASS, FAIL
    inbox = _temp_inbox("dry-run")

    spec = os.path.join(FIXTURES, "dry-run", "spec.yaml")
    r = run("dry-run: no files written", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--dry-run", "--created-at", "2026-06-08"])
    if r.returncode != 0:
        return

    files = non_roster_files(inbox)
    if files:
        FAIL += 1
        print(f"  [FAIL] dry-run: files were written: {files}")
    else:
        pass  # ok

    # Check stdout contains task content
    if "task_id: dry-test" in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] dry-run: stdout missing task content")


def test_existing_file_fails():
    """Existing task file causes failure without overwrite."""
    global PASS, FAIL
    inbox = os.path.join(FIXTURES, "existing")
    spec = os.path.join(inbox, "spec.yaml")
    r = run("existing: fails", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-08"], expect_exit=1)

    # Verify original file is unchanged
    task_file = os.path.join(inbox, "task-ExistingWorker-already-assigned.md")
    if os.path.exists(task_file):
        with open(task_file) as f:
            content = f.read()
        if "Pre-existing task file" in content:
            pass  # unchanged
        else:
            FAIL += 1
            print("  [FAIL] existing: task file was overwritten")
    else:
        FAIL += 1
        print("  [FAIL] existing: task file disappeared")


def test_missing_field_fails():
    """Missing required field fails with clear error."""
    global PASS, FAIL
    inbox = _temp_inbox("missing-field")

    spec = os.path.join(FIXTURES, "missing-field", "spec.yaml")
    r = run("missing-field: fails", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-08"], expect_exit=1)

    # No files should be written
    files = non_roster_files(inbox)
    if files:
        FAIL += 1
        print(f"  [FAIL] missing-field: files were written: {files}")

    # stderr should mention the missing field
    if "role" in r.stderr:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] missing-field: stderr missing 'role': {r.stderr[:200]}")


def test_invalid_enum_fails():
    """Invalid enum value fails."""
    global PASS, FAIL
    inbox = _temp_inbox("invalid-enum")

    spec = os.path.join(FIXTURES, "invalid-enum", "spec.yaml")
    r = run("invalid-enum: fails", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-08"], expect_exit=1)

    files = non_roster_files(inbox)
    if files:
        FAIL += 1
        print(f"  [FAIL] invalid-enum: files were written: {files}")


def test_acceptance_typo_fails():
    """Spec key 'acceptance' fails fast instead of generating empty criteria."""
    global PASS, FAIL
    inbox = _temp_inbox("acceptance-typo")
    spec = os.path.join(inbox, "spec-acceptance-typo.yaml")
    with open(os.path.join(FIXTURES, "valid", "spec.yaml"), encoding="utf-8") as f:
        content = f.read().replace("acceptance_criteria:", "acceptance:", 1)
    with open(spec, "w", encoding="utf-8") as f:
        f.write(content)

    r = run(
        "acceptance-typo: fails",
        [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox],
        expect_exit=1,
    )
    if "use acceptance_criteria" not in r.stderr:
        FAIL += 1
        print(f"  [FAIL] acceptance-typo: stderr missing hint: {r.stderr[:300]}")


def test_empty_acceptance_fails():
    """Empty acceptance_criteria fails before task generation."""
    global PASS, FAIL
    inbox = _temp_inbox("empty-acceptance")
    spec = os.path.join(inbox, "spec-empty-acceptance.yaml")
    with open(os.path.join(FIXTURES, "valid", "spec.yaml"), encoding="utf-8") as f:
        content = f.read().replace(
            "acceptance_criteria: Badge URL points to the correct CI pipeline.; README renders correctly.",
            "acceptance_criteria: ",
            1,
        )
    with open(spec, "w", encoding="utf-8") as f:
        f.write(content)

    r = run(
        "empty-acceptance: fails",
        [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox],
        expect_exit=1,
    )
    if "acceptance_criteria" not in r.stderr:
        FAIL += 1
        print(f"  [FAIL] empty-acceptance: stderr missing field: {r.stderr[:300]}")


def test_invalid_date_in_spec():
    """Spec with invalid created_at fails."""
    global PASS, FAIL
    inbox = _temp_inbox("invalid-date")

    spec = os.path.join(FIXTURES, "invalid-date", "spec.yaml")
    r = run("invalid-date (spec): fails", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-08"], expect_exit=1)

    files = non_roster_files(inbox)
    if files:
        FAIL += 1
        print(f"  [FAIL] invalid-date (spec): files were written: {files}")

    if "not-a-date" in r.stderr or "created_at" in r.stderr:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] invalid-date (spec): stderr missing date error: {r.stderr[:200]}")


def test_invalid_date_cli_flag():
    """--created-at with invalid date fails when spec omits created_at."""
    global PASS, FAIL
    inbox = _temp_inbox("invalid-date-cli")

    spec = os.path.join(FIXTURES, "invalid-date", "spec-no-date.yaml")
    r = run("invalid-date (cli): fails", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "not-a-date"], expect_exit=1)

    files = non_roster_files(inbox)
    if files:
        FAIL += 1
        print(f"  [FAIL] invalid-date (cli): files were written: {files}")

    if "not-a-date" in r.stderr or "created_at" in r.stderr:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] invalid-date (cli): stderr missing date error: {r.stderr[:200]}")


def test_unsafe_id_fails():
    """task_id with path separators fails."""
    global PASS, FAIL
    inbox = _temp_inbox("unsafe-id")

    spec = os.path.join(FIXTURES, "unsafe-id", "spec.yaml")
    r = run("unsafe-id: fails", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-08"], expect_exit=1)

    files = non_roster_files(inbox)
    if files:
        FAIL += 1
        print(f"  [FAIL] unsafe-id: files were written: {files}")

    if "unsafe" in r.stderr or "task_id" in r.stderr:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] unsafe-id: stderr missing safety error: {r.stderr[:200]}")


def test_zh_handoff():
    """Spec with handoff.language: zh produces Chinese handoff."""
    global PASS, FAIL
    inbox = _temp_inbox("zh-handoff")

    spec = os.path.join(FIXTURES, "zh-handoff", "spec.yaml")
    r = run("zh-handoff: generate", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-08"])
    if r.returncode != 0:
        return

    # Check handoff is Chinese
    if "你是 DocsWorker。" in r.stdout:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] zh-handoff: missing Chinese identity line. stdout:\n{r.stdout[:500]}")
    if "不要 commit/push。" in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] zh-handoff: missing Chinese '不要 commit/push。'")
    if "不要新建 worktree。" in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] zh-handoff: missing Chinese '不要新建 worktree。'")
    # Should NOT contain English identity line
    if "You are DocsWorker." in r.stdout:
        FAIL += 1
        print("  [FAIL] zh-handoff: English identity line found in Chinese handoff")

    # Task file should still pass validator
    task_file = os.path.join(inbox, "task-DocsWorker-fix-readme-typo-zh.md")
    if os.path.exists(task_file):
        run("zh-handoff: task passes validator", [sys.executable, "-B", VALIDATOR, task_file])
    else:
        FAIL += 1
        print("  [FAIL] zh-handoff: task file not created")


def test_cli_lang_override():
    """--handoff-language zh overrides spec handoff.language: en."""
    global PASS, FAIL
    inbox = _temp_inbox("cli-lang-override")

    spec = os.path.join(FIXTURES, "cli-lang-override", "spec.yaml")
    r = run("cli-lang-override: generate", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-08", "--handoff-language", "zh"])
    if r.returncode != 0:
        return

    # CLI --handoff-language zh should override spec's en
    if "你是 DocsWorker。" in r.stdout:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] cli-lang-override: missing Chinese identity line. stdout:\n{r.stdout[:500]}")
    if "You are DocsWorker." in r.stdout:
        FAIL += 1
        print("  [FAIL] cli-lang-override: English identity line found (CLI override failed)")


def test_unsupported_lang_no_template_fails():
    """Unsupported language without handoff.template fails — no copy-paste English fallback."""
    global PASS, FAIL
    inbox = _temp_inbox("unsupported-lang-notemplate")

    spec = os.path.join(FIXTURES, "unsupported-lang", "spec-ja-no-template.yaml")
    r = run("unsupported-lang (no template): fails", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-08"], expect_exit=1)

    # Must NOT produce a copy-paste-ready English handoff
    if "You are DocsWorker." in r.stdout:
        FAIL += 1
        print("  [FAIL] unsupported-lang: English handoff produced for unsupported language")
    # Must NOT write any files
    files = non_roster_files(inbox)
    if files:
        FAIL += 1
        print(f"  [FAIL] unsupported-lang: files were written: {files}")
    # stderr should mention the language and localization requirement
    if "ja" in r.stderr and ("not built in" in r.stderr or "localize" in r.stderr):
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] unsupported-lang: stderr missing localization warning: {r.stderr[:300]}")


def test_unsupported_lang_with_template():
    """Unsupported language with handoff.template succeeds using custom template."""
    global PASS, FAIL
    inbox = _temp_inbox("unsupported-lang-template")

    spec = os.path.join(FIXTURES, "unsupported-lang", "spec-ja-with-template.yaml")
    r = run("unsupported-lang (with template): generate", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-08"])
    if r.returncode != 0:
        return

    # Should contain Japanese text from template
    if "あなたは DocsWorker です" in r.stdout:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] unsupported-lang-template: missing Japanese identity line. stdout:\n{r.stdout[:500]}")
    # Should NOT contain English identity line
    if "You are DocsWorker." in r.stdout:
        FAIL += 1
        print("  [FAIL] unsupported-lang-template: English identity line found")

    # Task file should pass validator
    task_file = os.path.join(inbox, "task-DocsWorker-supported-ja-template.md")
    if os.path.exists(task_file):
        run("unsupported-lang-template: task passes validator", [sys.executable, "-B", VALIDATOR, task_file])
    else:
        FAIL += 1
        print("  [FAIL] unsupported-lang-template: task file not created")


def test_confirm_dispatch():
    """--confirm-dispatch appends TASK_DISPATCHED event after delivery."""
    global PASS, FAIL
    inbox = _temp_inbox("confirm-dispatch")

    # First, generate a task file
    spec = os.path.join(FIXTURES, "confirm-dispatch", "spec.yaml")
    r = run("confirm-dispatch: generate task", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-12"])
    if r.returncode != 0:
        return
    confirm_line = next(
        (line.strip() for line in r.stdout.splitlines()
         if "--confirm-dispatch confirm-test" in line),
        "",
    )
    expected_parts = (
        "--confirm-dispatch confirm-test",
        "--confirm-dispatch-agent TestWorker",
        f"--inbox {inbox}",
    )
    if not confirm_line or not all(part in confirm_line for part in expected_parts):
        FAIL += 1
        print("  [FAIL] confirm-dispatch: generated confirmation command is incomplete")

    # Verify TASK_ASSIGNED event exists but no TASK_DISPATCHED
    events_file = os.path.join(inbox, "events.jsonl")
    if os.path.exists(events_file):
        with open(events_file) as f:
            content = f.read()
        if "TASK_ASSIGNED" in content:
            pass
        else:
            FAIL += 1
            print("  [FAIL] confirm-dispatch: TASK_ASSIGNED not in events.jsonl")
        if "TASK_DISPATCHED" in content:
            FAIL += 1
            print("  [FAIL] confirm-dispatch: TASK_DISPATCHED should not be in events yet")
    else:
        FAIL += 1
        print("  [FAIL] confirm-dispatch: events.jsonl not created")

    # Now confirm dispatch using the exact command arguments printed by the tool.
    confirm_args = confirm_line.split()[3:]
    r = run(
        "confirm-dispatch: confirm delivery",
        [sys.executable, "-B", SCRIPT] + confirm_args + ["--created-at", "2026-06-12"],
    )
    if r.returncode != 0:
        return

    # Verify TASK_DISPATCHED event now exists
    if os.path.exists(events_file):
        with open(events_file) as f:
            content = f.read()
        if "TASK_DISPATCHED" in content:
            pass
        else:
            FAIL += 1
            print("  [FAIL] confirm-dispatch: TASK_DISPATCHED not in events after confirmation")
        # Validate the event log
        run("confirm-dispatch: events validates", [sys.executable, "-B", VALIDATOR, events_file])
    else:
        FAIL += 1
        print("  [FAIL] confirm-dispatch: events.jsonl missing after confirmation")

    # Test idempotency - second confirmation should succeed without duplicate
    r = run("confirm-dispatch: idempotent", [sys.executable, "-B", SCRIPT, "--confirm-dispatch", "confirm-test", "--confirm-dispatch-agent", "TestWorker", "--inbox", inbox, "--created-at", "2026-06-12"])
    if r.returncode != 0:
        FAIL += 1
        print("  [FAIL] confirm-dispatch: idempotent confirmation failed")
    else:
        # Count TASK_DISPATCHED events - should be exactly 1
        with open(events_file) as f:
            content = f.read()
        count = content.count("TASK_DISPATCHED")
        if count == 1:
            pass
        else:
            FAIL += 1
            print(f"  [FAIL] confirm-dispatch: expected 1 TASK_DISPATCHED event, found {count}")


def test_confirm_dispatch_missing_task():
    """--confirm-dispatch for non-existent task fails."""
    global PASS, FAIL
    inbox = os.path.join(_SHARED_TEMP, "confirm-dispatch")
    if not os.path.isdir(inbox):
        FAIL += 1
        print("  [SKIP] confirm-dispatch-missing: temp dir not found (run confirm-dispatch test first)")
        return

    r = run("confirm-dispatch-missing: fails", [sys.executable, "-B", SCRIPT, "--confirm-dispatch", "nonexistent-task", "--inbox", inbox, "--created-at", "2026-06-12"], expect_exit=1)

    # stderr should mention the missing task
    if "no task file found" in r.stderr:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] confirm-dispatch-missing: stderr missing error: {r.stderr[:200]}")


def test_release_operator_generates_valid_task():
    """Release-Operator spec produces a task with commit_push: approved and ## Release Operations Scope."""
    global PASS, FAIL
    inbox = _temp_inbox("release-operator")

    spec = os.path.join(FIXTURES, "release-operator", "spec.yaml")
    r = run("release-operator: generate", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-12"])
    if r.returncode != 0:
        return

    # Check frontmatter has commit_push: approved and network_access: none (from spec)
    task_file = os.path.join(inbox, "task-ReleaseBot-release-changelog-update.md")
    if os.path.exists(task_file):
        with open(task_file) as f:
            content = f.read()
        if "commit_push: approved" in content:
            pass
        else:
            FAIL += 1
            print("  [FAIL] release-operator: frontmatter missing commit_push: approved")
        if "network_access: none" in content:
            pass
        else:
            FAIL += 1
            print("  [FAIL] release-operator: frontmatter missing network_access: none")
        if "## Release Operations Scope" in content:
            pass
        else:
            FAIL += 1
            print("  [FAIL] release-operator: task body missing ## Release Operations Scope")
    else:
        FAIL += 1
        print("  [FAIL] release-operator: task file not created")

    # Handoff must NOT say "Do not commit or push" for approved commit_push
    if "Do not commit or push" in r.stdout:
        FAIL += 1
        print("  [FAIL] release-operator: handoff says 'Do not commit or push' but commit_push is approved")
    if "Release Operations Scope" in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] release-operator: handoff missing 'Release Operations Scope' reference")

    # Task file should pass validator (has Release Operations Scope section)
    if os.path.exists(task_file):
        run("release-operator: task passes validator", [sys.executable, "-B", VALIDATOR, task_file])
    else:
        FAIL += 1
        print("  [FAIL] release-operator: task file not found for validator check")


def test_release_operator_zh_handoff():
    """Release-Operator with zh handoff produces correct Chinese commit/push guidance."""
    global PASS, FAIL
    inbox = _temp_inbox("release-operator-zh")

    spec = os.path.join(FIXTURES, "release-operator", "spec-zh.yaml")
    # spec-zh is same as spec but with handoff.language: zh
    r = run("release-operator-zh: generate", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-12"])
    if r.returncode != 0:
        return

    # Chinese handoff must NOT say "不要 commit/push"
    if "不要 commit/push" in r.stdout:
        FAIL += 1
        print("  [FAIL] release-operator-zh: handoff says '不要 commit/push' but commit_push is approved")
    if "Release Operations Scope" in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] release-operator-zh: handoff missing 'Release Operations Scope' reference")


def test_sequence_serial_en():
    """Serial handoff.sequence produces English explicit instruction before commit/push."""
    global PASS, FAIL
    inbox = _temp_inbox("sequence-serial")

    spec = os.path.join(FIXTURES, "sequence-serial", "spec.yaml")
    r = run("sequence-serial: generate", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-13"])
    if r.returncode != 0:
        return

    # Check explicit instruction and final marker appear in the handoff.
    if "Final line of your user-facing completion reply must be: Completed task: #37" in r.stdout:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] sequence-serial: missing explicit instruction for 'Completed task: #37'. stdout:\n{r.stdout[:500]}")

    # Check marker is the final handoff line before tool notes.
    if "Completed task: #37\n\nNOTE:" in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] sequence-serial: marker must be final handoff line")

    # Check instruction comes after "Do not commit or push."
    instruction_pos = r.stdout.find("Final line of your user-facing completion reply")
    commit_pos = r.stdout.find("Do not commit or push.")
    if instruction_pos >= 0 and commit_pos >= 0 and commit_pos < instruction_pos:
        pass
    else:
        FAIL += 1
        print("  [FAIL] sequence-serial: explicit instruction must appear after commit/push line")

    # Check "Do not commit or push." is still present as the final safety line
    if "Do not commit or push." in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] sequence-serial: missing 'Do not commit or push.'")
    if "afc-report.py" in r.stdout and "--task" in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] sequence-serial: missing concrete report command")
    task_file = os.path.join(inbox, "task-SeqWorker-serial-seq-task.md")
    events_file = os.path.join(inbox, "events.jsonl")
    if os.path.exists(task_file):
        with open(task_file, encoding="utf-8") as f:
            task_text = f.read()
        if "completion_marker: Completed task: #37" not in task_text:
            FAIL += 1
            print("  [FAIL] sequence-serial: task missing completion_marker")
    else:
        FAIL += 1
        print("  [FAIL] sequence-serial: task file not created")
    if os.path.exists(events_file):
        with open(events_file, encoding="utf-8") as f:
            evt = json.loads(f.readline())
        if evt.get("completion_marker") != "Completed task: #37":
            FAIL += 1
            print("  [FAIL] sequence-serial: event missing completion_marker")


def test_sequence_parallel_en():
    """Parallel handoff.sequence (e.g. 32.1) produces explicit instruction with 'Completed task: #32.1'."""
    global PASS, FAIL
    inbox = _temp_inbox("sequence-parallel")

    spec = os.path.join(FIXTURES, "sequence-parallel", "spec.yaml")
    r = run("sequence-parallel: generate", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-13"])
    if r.returncode != 0:
        return

    if "Final line of your user-facing completion reply must be: Completed task: #32.1" in r.stdout:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] sequence-parallel: missing explicit instruction for 'Completed task: #32.1'. stdout:\n{r.stdout[:500]}")
    if "Completed task: #32.1\n\nNOTE:" not in r.stdout:
        FAIL += 1
        print("  [FAIL] sequence-parallel: marker must be final handoff line")

    # Verify commit/push line still present
    if "Do not commit or push." in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] sequence-parallel: missing 'Do not commit or push.'")


def test_sequence_invalid():
    """Invalid handoff.sequence value is rejected."""
    global PASS, FAIL
    inbox = _temp_inbox("sequence-invalid")

    spec = os.path.join(FIXTURES, "sequence-invalid", "spec.yaml")
    r = run("sequence-invalid: fails", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-13"], expect_exit=1)

    files = non_roster_files(inbox)
    if files:
        FAIL += 1
        print(f"  [FAIL] sequence-invalid: files were written: {files}")

    if "sequence" in r.stderr:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] sequence-invalid: stderr missing sequence error: {r.stderr[:300]}")


def test_sequence_zh():
    """Chinese handoff with sequence produces explicit instruction before '不要 commit/push。'."""
    global PASS, FAIL
    inbox = _temp_inbox("sequence-zh")

    spec = os.path.join(FIXTURES, "sequence-zh", "spec.yaml")
    r = run("sequence-zh: generate", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-13"])
    if r.returncode != 0:
        return

    if "最终回复最后一行必须是：完成任务：#37" in r.stdout:
        pass
    else:
        FAIL += 1
        print(f"  [FAIL] sequence-zh: missing explicit instruction '完成后，在用户对话回复的最后一行写：完成任务：#37'. stdout:\n{r.stdout[:500]}")

    if "完成任务：#37\n\nNOTE:" in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] sequence-zh: marker must be final handoff line")

    # Check instruction comes after "不要 commit/push。"
    instruction_pos = r.stdout.find("最终回复最后一行必须是：完成任务：#37")
    commit_pos = r.stdout.find("不要 commit/push")
    if instruction_pos >= 0 and commit_pos >= 0 and commit_pos < instruction_pos:
        pass
    else:
        FAIL += 1
        print("  [FAIL] sequence-zh: explicit instruction must appear after commit/push line")

    if "不要 commit/push" in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] sequence-zh: missing '不要 commit/push'")


def test_sequence_absent_auto_allocates():
    """Spec without handoff.sequence auto-allocates a sequence from the .seq counter."""
    global PASS, FAIL
    inbox = _temp_inbox("sequence-absent")

    spec = os.path.join(FIXTURES, "valid", "spec.yaml")
    r = run("sequence-absent: generate", [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-08"])
    if r.returncode != 0:
        return

    # First task in a fresh inbox auto-allocates #1.
    if "Completed task: #1" in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] sequence-absent: expected auto-allocated 'Completed task: #1'")

    # The counter file must persist the consumed number.
    seq_path = os.path.join(inbox, ".seq")
    if os.path.isfile(seq_path) and open(seq_path, encoding="utf-8").read().strip() == "1":
        pass
    else:
        FAIL += 1
        print("  [FAIL] sequence-absent: .seq counter did not persist value 1")

    # Must still have the standard ending
    if "Do not commit or push." in r.stdout:
        pass
    else:
        FAIL += 1
        print("  [FAIL] sequence-absent: missing 'Do not commit or push.'")


def test_sequence_reservation_is_concurrent_safe():
    global PASS, FAIL
    inbox = _temp_inbox("sequence-concurrent")
    scripts_dir = os.path.dirname(SCRIPT)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("afc_assign_concurrency", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = []
    lock = threading.Lock()

    def reserve():
        value = module.reserve_sequence(inbox)
        with lock:
            values.append(value)

    threads = [threading.Thread(target=reserve) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    ok = sorted(values) == list(range(1, 9))
    if ok:
        PASS += 1
        print("  [PASS] sequence-concurrent: unique reservations")
    else:
        FAIL += 1
        print("  [FAIL] sequence-concurrent: values={}".format(values))


def test_sequence_reservation_recovers_dead_owner_lock():
    global PASS, FAIL
    inbox = _temp_inbox("sequence-abandoned-lock")
    scripts_dir = os.path.dirname(SCRIPT)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location("afc_assign_abandoned_lock", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lock_path = os.path.join(inbox, module.SEQUENCE_LOCK_FILENAME)
    with open(lock_path, "w", encoding="ascii") as handle:
        handle.write("99999999\n")
    value = module.reserve_sequence(inbox)
    ok = value == 1 and not os.path.exists(lock_path)
    if ok:
        PASS += 1
        print("  [PASS] sequence-abandoned-lock: reclaimed dead owner")
    else:
        FAIL += 1
        print("  [FAIL] sequence-abandoned-lock: value={} lock_exists={}".format(
            value, os.path.exists(lock_path)))


def test_attribution_fields_in_event():
    """--coordinator-thread-id / --trace-id / --coordinator-root-thread-id land in
    the task frontmatter and the TASK_ASSIGNED event (lightweight instrumentation)."""
    global PASS, FAIL
    inbox = _temp_inbox("attribution")

    spec = os.path.join(FIXTURES, "valid", "spec.yaml")
    r = run(
        "attribution: generate with thread ids",
        [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox,
         "--created-at", "2026-06-14",
         "--coordinator-thread-id", "COORD-123",
         "--trace-id", "TR-9",
         "--coordinator-root-thread-id", "ROOT-1"],
    )
    if r.returncode != 0:
        return

    # Task frontmatter carries the coordinator thread id.
    task_file = os.path.join(inbox, "task-DocsWorker-fix-readme-typo.md")
    if os.path.exists(task_file):
        with open(task_file, encoding="utf-8") as f:
            content = f.read()
        if "coordinator_thread_id: COORD-123" not in content:
            FAIL += 1
            print("  [FAIL] attribution: task frontmatter missing coordinator_thread_id")
    else:
        FAIL += 1
        print("  [FAIL] attribution: task file not created")

    # TASK_ASSIGNED event carries attribution fields, phase, and a timestamp.
    events_file = os.path.join(inbox, "events.jsonl")
    if os.path.exists(events_file):
        run("attribution: events validates", [sys.executable, "-B", VALIDATOR, events_file])
        with open(events_file, encoding="utf-8") as f:
            evt = json.loads(f.readline())
        checks = {
            "coordinator_thread_id": "COORD-123",
            "trace_id": "TR-9",
            "coordinator_root_thread_id": "ROOT-1",
            "phase": "assignment",
        }
        for key, expected in checks.items():
            if evt.get(key) != expected:
                FAIL += 1
                print(f"  [FAIL] attribution: event {key} is {evt.get(key)!r}, expected {expected!r}")
        if not evt.get("occurred_at"):
            FAIL += 1
            print("  [FAIL] attribution: event missing occurred_at timestamp")
    else:
        FAIL += 1
        print("  [FAIL] attribution: events.jsonl not created")


def test_attribution_absent_byte_compatible():
    """Without attribution flags, the event carries no attribution keys."""
    global PASS, FAIL
    inbox = _temp_inbox("attribution-absent")

    spec = os.path.join(FIXTURES, "valid", "spec.yaml")
    clean_env = os.environ.copy()
    clean_env.pop("CODEX_THREAD_ID", None)
    clean_env.pop("CODEX_ROOT_THREAD_ID", None)
    r = run(
        "attribution-absent: generate without thread ids",
        [sys.executable, "-B", SCRIPT, "--spec", spec, "--inbox", inbox, "--created-at", "2026-06-14"],
        env=clean_env,
    )
    if r.returncode != 0:
        return

    events_file = os.path.join(inbox, "events.jsonl")
    if os.path.exists(events_file):
        with open(events_file, encoding="utf-8") as f:
            evt = json.loads(f.readline())
        # trace_id falls back to task_id by design; thread ids must be absent.
        for key in ("coordinator_thread_id", "coordinator_root_thread_id"):
            if key in evt:
                FAIL += 1
                print(f"  [FAIL] attribution-absent: unexpected {key} in event without the flag")
    else:
        FAIL += 1
        print("  [FAIL] attribution-absent: events.jsonl not created")


def main():
    global _SHARED_TEMP
    print("Running afc-assign.py fixture tests...")
    print()
    _SHARED_TEMP = tempfile.mkdtemp(prefix="afc_assign_test_")
    try:
        test_valid_generates_valid_task()
        test_roster_missing_blocks_full_assignment()
        test_roster_placeholder_blocks_full_assignment()
        test_roster_incomplete_blocks_full_assignment()
        test_unmatched_worker_alias_blocks_no_subagent_fallback()
        test_matched_internal_worker_route_blocks_no_artifacts()
        test_builtin_subagent_alias_blocks_no_artifacts()
        test_status_semantics()
        test_dry_run_no_files()
        test_existing_file_fails()
        test_missing_field_fails()
        test_invalid_enum_fails()
        test_acceptance_typo_fails()
        test_empty_acceptance_fails()
        test_invalid_date_in_spec()
        test_invalid_date_cli_flag()
        test_unsafe_id_fails()
        test_zh_handoff()
        test_cli_lang_override()
        test_unsupported_lang_no_template_fails()
        test_unsupported_lang_with_template()
        test_confirm_dispatch()
        test_confirm_dispatch_missing_task()
        test_release_operator_generates_valid_task()
        test_release_operator_zh_handoff()
        test_sequence_serial_en()
        test_sequence_parallel_en()
        test_sequence_invalid()
        test_sequence_zh()
        test_sequence_absent_auto_allocates()
        test_sequence_reservation_is_concurrent_safe()
        test_sequence_reservation_recovers_dead_owner_lock()
        test_attribution_fields_in_event()
        test_attribution_absent_byte_compatible()
    finally:
        # Clean up shared temp dir
        shutil.rmtree(_SHARED_TEMP, onerror=_on_rm_error)
    print()
    print(f"Results: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


def _on_rm_error(func, path, exc_info):
    """Handle PermissionError on Windows by retrying after clearing read-only."""
    import stat
    exc_type, exc_value, _ = exc_info
    if exc_type is PermissionError or (isinstance(exc_value, OSError) and getattr(exc_value, 'winerror', None) in (5, 32, 145)):
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        try:
            func(path)
        except Exception:
            pass
    else:
        pass


if __name__ == "__main__":
    sys.exit(main())
