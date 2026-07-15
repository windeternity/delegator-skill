#!/usr/bin/env python3
"""Minimal end-to-end dogfood fixture for agent-file-coordination.

Proves the smallest closed loop is not broken:

  afc-init -> afc-assign -> fake report -> afc-status -> afc-poll
  -> fake coordinator verdict -> summarize-codex-usage
  -> validate-agent-inbox --cross-check

Uses a temporary directory for the project root.  Never writes a real
.agent-inbox into the repository.  Deterministic (fixed date).
Cleans up the temporary directory on exit.

Python stdlib only.  Intended to be run from the repository root:

    python -B examples/fixtures/e2e-dogfood/run-tests.py

Exit codes:
    0   all stages passed
    1   at least one stage failed
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

AFC_INIT_SH = os.path.join(REPO_ROOT, "scripts", "afc-init.sh")
AFC_ASSIGN = os.path.join(REPO_ROOT, "scripts", "afc-assign.py")
AFC_STATUS = os.path.join(REPO_ROOT, "scripts", "afc-status.py")
AFC_POLL = os.path.join(REPO_ROOT, "scripts", "afc-poll.py")
SUMMARIZE = os.path.join(REPO_ROOT, "scripts", "summarize-codex-usage.py")
VALIDATOR = os.path.join(REPO_ROOT, "scripts", "validate-agent-inbox.py")
CODEX_FIXTURE = os.path.join(
    REPO_ROOT, "examples", "fixtures", "codex-usage", "valid-single-label.jsonl"
)

FIXED_DATE = "2026-06-09"
TASK_ID = "e2e-smoke-001"
AGENT_NAME = "Implementer"
REPORT_FILENAME = f"report-{AGENT_NAME}-{TASK_ID}.md"
VERDICT_FILENAME = f"verdict-{TASK_ID}.md"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
PASS = 0
FAIL = 0


def run(label, cmd, expect_exit=0):
    """Run *cmd*, assert *expect_exit*. Returns (ok, stdout, stderr)."""
    global PASS, FAIL
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == expect_exit
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {label} (exit={r.returncode}, expected={expect_exit})")
    if not ok:
        FAIL += 1
        print(f"    stdout: {r.stdout[:500]}")
        print(f"    stderr: {r.stderr[:500]}")
    else:
        PASS += 1
    return ok, r.stdout, r.stderr


def check(label, condition, detail=""):
    """Simple boolean assertion with PASS/FAIL output."""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}: {detail}")


def find_bash():
    """Return bash path or None (cross-platform)."""
    bash = shutil.which("bash")
    if not bash:
        return None
    try:
        r = subprocess.run(
            [bash, "-c", "printf ready"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return None
    return bash if r.returncode == 0 and r.stdout == "ready" else None


def detect_bash_path_style():
    """Return the mount style for the local bash.

    'wsl'   -> Windows drives under /mnt/<drive>/
    'git'   -> Windows drives under /<drive>/
    'unix'  -> native Unix shell; paths are already POSIX
    """
    try:
        r = subprocess.run(
            ["bash", "-c", "uname -r"],
            capture_output=True, text=True, timeout=5,
        )
        out = r.stdout.lower()
    except Exception:
        return "unix"
    if "microsoft" in out or "wsl" in out:
        return "wsl"
    return "unix"


BASH_PATH_STYLE = detect_bash_path_style()


def to_bash_path(win_path):
    """Convert a path for the local bash variant."""
    s = win_path.replace("\\", "/")
    if BASH_PATH_STYLE == "wsl" and len(s) >= 2 and s[1] == ":":
        return f"/mnt/{s[0].lower()}" + s[2:]
    if BASH_PATH_STYLE == "git" and len(s) >= 2 and s[1] == ":":
        return f"/{s[0].lower()}" + s[2:]
    return s


def write_usable_roster(inbox):
    """Hydrate the init template with one external user-relay worker."""
    roster = f"""---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---

# Agent Roster

<!-- SESSION PREFERENCES
Default CAL: CAL-1
Execution preference: fixture external user-relay
Available resources: external user-relay workers
Available now: {AGENT_NAME}
Model preference order: fixture model
Avoid / unavailable: none
Smoke tests: fixture
Confirmed: {FIXED_DATE}
Change policy: fixture
-->

| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| {AGENT_NAME} | implementer | external-chat | user-relay-model | user-relay:{AGENT_NAME} | task-only | no | yes | read_only | yes | no | manual_needed | e2e fixture work | none | external user-relay worker |
"""
    with open(os.path.join(inbox, "AGENT_ROSTER.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(roster)


# ---------------------------------------------------------------------------
# Spec content (inline to keep the fixture self-contained)
# ---------------------------------------------------------------------------

def normalized_workspace_path(path):
    """Return a forward-slash absolute path suitable for workspace.path."""
    return os.path.abspath(path).replace("\\", "/")


def make_spec_content(project_root):
    """Return the afc-assign spec string using the actual project root."""
    ws_path = normalized_workspace_path(project_root)
    return f"""\
task_id: {TASK_ID}
agent_name: {AGENT_NAME}
role: implementer
protocol_mode: task-only
coordinator_authority: no
validation_tier: no-test-needed
report_path: .agent-inbox/{REPORT_FILENAME}
purpose: Minimal e2e smoke test
workspace.mode: read_only_shared
workspace.path: {ws_path}
workspace.may_create_worktree: no
permission_scope.modify_source: no
permission_scope.run_commands: none
routing.estimated_direct_minutes: 240
routing.independent_workstreams: 1
routing.smallest_workstream_minutes: 240
routing.specialized_capability: no
routing.high_risk_independent_review: no
routing.external_worker_required: no
routing.semantic_change: no
routing.expected_rounds: 1
routing.context_bytes: 64
routing.requested_mode: auto
non_goals: everything else
acceptance_criteria: e2e loop completes
evidence_to_report: stdout log
created_at: {FIXED_DATE}
"""

REPORT_CONTENT = f"""\
---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: {TASK_ID}
agent_name: {AGENT_NAME}
verdict: GO
changed_files:
  - none
evidence_refs:
  - task-file
evidence_trust:
  trust_level: self_claim
  untrusted_inputs_seen: no
  prompt_injection_suspected: no
  permission_escalation_requested: no
guardrails:
  role_boundary_followed: yes
  coordinator_verdict_given: no
  permission_scope_expanded: no
  secrets_private_data_printed: no
  production_default_behavior_changed: no
  commit_push_done: no
  destructive_command_done: no
validation:
  tier: no-test-needed
  result: pass
reported_at: {FIXED_DATE}
---

# Report - {AGENT_NAME} {TASK_ID}

## Summary

Minimal e2e smoke test completed successfully.
"""

VERDICT_CONTENT = f"""\
---
schema: agent-file-coordination/coordinator-verdict
schema_version: 0.1.0
task_id: {TASK_ID}
verdict: GO
score: 14
score_breakdown:
  scope_control: 2
  evidence_quality: 2
  validation: 2
  safety_privacy: 2
  reproducibility: 2
  conflict_awareness: 2
  prompt_injection_resistance: 2
evidence_checked:
  - task-file
  - report-file
  - status-board
blockers:
  - none
follow_up:
  - none
---

# Verdict - {TASK_ID}

## GO

All e2e stages passed.
"""

# Minimal valid Codex usage JSONL (one turn.completed event)
MINI_CODEX_JSONL = (
    '{"type":"thread.started","thread_id":"e2e-smoke"}\n'
    '{"type":"turn.completed","turn_id":"t1",'
    '"usage":{"input_tokens":100,"output_tokens":50}}\n'
)


# ---------------------------------------------------------------------------
# Test stages
# ---------------------------------------------------------------------------

def stage_a_init(tmp_project, bash_path):
    """A. afc-init.sh initializes .agent-inbox from templates."""
    print("\n--- Stage A: afc-init ---")
    inbox = os.path.join(tmp_project, ".agent-inbox")
    ok, _, _ = run(
        "afc-init.sh",
        [bash_path, to_bash_path(AFC_INIT_SH),
         "-p", to_bash_path(tmp_project), "-d", FIXED_DATE],
        expect_exit=0,
    )
    if ok:
        for name in ("AGENT_ROSTER.md", "STATUS.md", "WORKTREE_LOCKS.md", "events.jsonl"):
            check(f"  {name} exists", os.path.isfile(os.path.join(inbox, name)))
        write_usable_roster(inbox)
        check("  AGENT_ROSTER.md hydrated", os.path.isfile(os.path.join(inbox, "AGENT_ROSTER.md")))
    return ok


def stage_b_assign(tmp_project):
    """B+C. Create spec, run afc-assign, verify task file + handoff + event."""
    print("\n--- Stage B+C: afc-assign ---")
    inbox = os.path.join(tmp_project, ".agent-inbox")
    spec_path = os.path.join(tmp_project, "e2e-spec.yaml")
    ws_path_normalized = normalized_workspace_path(tmp_project)
    with open(spec_path, "w", encoding="utf-8") as f:
        f.write(make_spec_content(tmp_project))

    ok, stdout, stderr = run(
        "afc-assign.py",
        [sys.executable, "-B", AFC_ASSIGN, "--spec", spec_path,
         "--inbox", inbox, "--created-at", FIXED_DATE],
        expect_exit=0,
    )
    if not ok:
        return False

    task_file = os.path.join(inbox, f"task-{AGENT_NAME}-{TASK_ID}.md")
    check("task file exists", os.path.isfile(task_file))
    check("handoff in stdout", f"You are {AGENT_NAME}." in stdout)

    # Verify events.jsonl has TASK_ASSIGNED
    events_path = os.path.join(inbox, "events.jsonl")
    has_assigned = False
    if os.path.isfile(events_path):
        with open(events_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                    if evt.get("event_type") == "TASK_ASSIGNED" and evt.get("task_id") == TASK_ID:
                        has_assigned = True
                except json.JSONDecodeError:
                    pass
    check("events.jsonl has TASK_ASSIGNED", has_assigned)

    # Validate task file individually
    run("task file validates", [sys.executable, "-B", VALIDATOR, task_file])

    # Assert task file contains the actual workspace path
    if os.path.isfile(task_file):
        with open(task_file, "r", encoding="utf-8") as f:
            task_content = f.read()
        check("task file has workspace.path",
              ws_path_normalized in task_content,
              f"expected {ws_path_normalized} in task file")

    return True


def stage_d_report(tmp_project):
    """D. Write fake worker report, validate it."""
    print("\n--- Stage D: fake worker report ---")
    inbox = os.path.join(tmp_project, ".agent-inbox")
    report_path = os.path.join(inbox, REPORT_FILENAME)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(REPORT_CONTENT)

    run("report validates", [sys.executable, "-B", VALIDATOR, report_path])


def stage_e_status(tmp_project):
    """E. Run afc-status, verify STATUS.md and events.jsonl."""
    print("\n--- Stage E: afc-status ---")
    inbox = os.path.join(tmp_project, ".agent-inbox")
    ws_path_normalized = normalized_workspace_path(tmp_project)
    ok, stdout, _ = run(
        "afc-status.py",
        [sys.executable, "-B", AFC_STATUS, "--updated-at", FIXED_DATE, inbox],
        expect_exit=0,
    )
    if not ok:
        return

    status_path = os.path.join(inbox, "STATUS.md")
    check("STATUS.md exists", os.path.isfile(status_path))

    with open(status_path, "r", encoding="utf-8") as f:
        content = f.read()
    check("STATUS.md has REPORTED", "REPORTED" in content)
    check("STATUS.md has coordinator_review", "coordinator_review" in content)
    check("STATUS.md has workspace.path",
          ws_path_normalized in content,
          f"expected {ws_path_normalized} in STATUS.md")

    # Verify events.jsonl has STATUS_UPDATED
    events_path = os.path.join(inbox, "events.jsonl")
    has_status_updated = False
    if os.path.isfile(events_path):
        with open(events_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                    if evt.get("event_type") == "STATUS_UPDATED":
                        has_status_updated = True
                except json.JSONDecodeError:
                    pass
    check("events.jsonl has STATUS_UPDATED", has_status_updated)


def stage_f_poll(tmp_project):
    """F. Run afc-poll, verify it detects the report."""
    print("\n--- Stage F: afc-poll ---")
    inbox = os.path.join(tmp_project, ".agent-inbox")
    ok, stdout, _ = run(
        "afc-poll.py",
        [sys.executable, "-B", AFC_POLL, "--json", inbox],
        expect_exit=0,
    )
    if not ok:
        return

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        check("afc-poll JSON output", False, f"not valid JSON: {stdout[:300]}")
        return

    check("afc-poll has new_reports",
          REPORT_FILENAME in data.get("new_reports", []))
    check("afc-poll has next_actions",
          len(data.get("next_actions", [])) > 0)


def stage_g_verdict(tmp_project):
    """G. Write fake coordinator verdict, validate it."""
    print("\n--- Stage G: fake coordinator verdict ---")
    inbox = os.path.join(tmp_project, ".agent-inbox")
    verdict_path = os.path.join(inbox, VERDICT_FILENAME)
    with open(verdict_path, "w", encoding="utf-8") as f:
        f.write(VERDICT_CONTENT)

    run("verdict validates", [sys.executable, "-B", VALIDATOR, verdict_path])


def stage_h_summarize(tmp_project):
    """H. Run summarize-codex-usage on a minimal valid JSONL."""
    print("\n--- Stage H: summarize-codex-usage ---")
    # Write a minimal JSONL in the temp project
    mini_log = os.path.join(tmp_project, "mini-usage.jsonl")
    with open(mini_log, "w", encoding="utf-8") as f:
        f.write(MINI_CODEX_JSONL)

    ok, stdout, _ = run(
        "summarize-codex-usage.py",
        [sys.executable, "-B", SUMMARIZE, "--json", f"smoke={mini_log}"],
        expect_exit=0,
    )
    if not ok:
        return
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        check("summarize JSON output", False, "not valid JSON")
        return
    check("summarize has per_label", "smoke" in data.get("per_label", {}))
    check("summarize has aggregate", "aggregate" in data)


def stage_i_cross_check(tmp_project):
    """I. validate-agent-inbox --cross-check on the full inbox."""
    print("\n--- Stage I: validate-agent-inbox --cross-check ---")
    inbox = os.path.join(tmp_project, ".agent-inbox")

    # WORKTREE_LOCKS remains template-generated, so we use --template-mode.
    # --cross-check runs alongside and verifies
    # cross-file consistency for real artifacts (task, report, verdict).
    run(
        "validate --template-mode --cross-check",
        [sys.executable, "-B", VALIDATOR,
         "--template-mode", "--cross-check", inbox],
        expect_exit=0,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    bash_path = find_bash()
    print(f"bash: {bash_path}")
    print(f"repo root: {REPO_ROOT}")
    print(f"fixed date: {FIXED_DATE}")

    if bash_path is None:
        print("\nSKIP: bash not found or not usable - cannot run e2e dogfood")
        print("      (This test is designed for CI where bash is available.)")
        return 0

    tmp_project = tempfile.mkdtemp(prefix="afc-e2e-dogfood-")
    print(f"temp project: {tmp_project}")
    print(f"bash path style: {BASH_PATH_STYLE}")
    try:
        if not stage_a_init(tmp_project, bash_path):
            print("\nFATAL: afc-init failed — skipping remaining stages")
        else:
            stage_b_assign(tmp_project)
            stage_d_report(tmp_project)
            stage_e_status(tmp_project)
            stage_f_poll(tmp_project)
            stage_g_verdict(tmp_project)
            stage_h_summarize(tmp_project)
            stage_i_cross_check(tmp_project)
    finally:
        shutil.rmtree(tmp_project, ignore_errors=True)

    print()
    print(f"Results: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
