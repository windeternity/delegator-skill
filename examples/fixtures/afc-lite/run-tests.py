#!/usr/bin/env python3
"""Fixture tests for afc-lite.py roster fail-closed behavior."""

import os
import shutil
import subprocess
import sys
import tempfile


ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPT = os.path.join(ROOT, "scripts", "afc-lite.py")
TEMPLATE_ROSTER = os.path.join(ROOT, "templates", "TEMPLATE_ROSTER.md")

PASS = 0
FAIL = 0


def run(label, cmd, expect_exit=0):
    global PASS, FAIL
    result = subprocess.run(cmd, capture_output=True, text=True)
    ok = result.returncode == expect_exit
    print("  [{}] {} (exit={}, expected={})".format(
        "PASS" if ok else "FAIL", label, result.returncode, expect_exit
    ))
    if ok:
        PASS += 1
    else:
        FAIL += 1
        print("    stdout: {}".format(result.stdout[:500]))
        print("    stderr: {}".format(result.stderr[:500]))
    return result


def write_file(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def make_workspace(roster_mode, default_cal="CAL-1"):
    root = tempfile.mkdtemp(prefix="afc-lite-")
    inbox = os.path.join(root, ".agent-inbox")
    if roster_mode != "missing":
        os.makedirs(inbox, exist_ok=True)
    if roster_mode == "placeholder":
        with open(TEMPLATE_ROSTER, encoding="utf-8") as handle:
            write_file(os.path.join(inbox, "AGENT_ROSTER.md"), handle.read())
    elif roster_mode == "incomplete":
        write_file(os.path.join(inbox, "AGENT_ROSTER.md"), """---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---
# Agent Roster

<!-- SESSION PREFERENCES
Default CAL: {default_cal}
Execution preference: fixture
Available resources: none
Available now: none
Model preference order: none
Avoid / unavailable: none
Smoke tests: none
Confirmed: 2026-06-29
Change policy: keep these defaults until the user asks to change them or a route becomes unavailable.
-->
""")
    elif roster_mode == "usable":
        write_file(os.path.join(inbox, "AGENT_ROSTER.md"), """---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---
# Agent Roster

<!-- SESSION PREFERENCES
Default CAL: CAL-1
Execution preference: fixture external worker
Available resources: external user-relay chat
Available now: LiteWorker
Model preference order: fixture model
Avoid / unavailable: none
Smoke tests: fixture
Confirmed: 2026-06-29
Change policy: keep these defaults until the user asks to change them or a route becomes unavailable.
-->

| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LiteWorker | implementer | external-chat | user-relay-model | user-relay:LiteWorker | task-only | no | yes | tests_only | yes | no | manual_needed | lite fixture work | none | external user-relay worker |
""".format(default_cal=default_cal))
    return root, inbox


def lite_cmd(root, inbox=None, agent="LiteWorker"):
    cmd = [
        sys.executable,
        "-B",
        SCRIPT,
        "--agent",
        agent,
        "--workspace",
        root,
        "--task",
        "Update one docs sentence.",
        "--allow-files",
        "README.md",
        "--validation",
        "none",
        "--estimated-direct-minutes",
        "30",
        "--external-worker-required",
        "yes",
        "--semantic-change",
        "no",
    ]
    if inbox:
        cmd.extend(["--inbox", inbox])
    return cmd


def test_missing_blocks():
    root, _ = make_workspace("missing")
    try:
        result = run("lite missing roster blocks", lite_cmd(root), expect_exit=1)
        if "roster inbox not found" not in result.stderr:
            raise AssertionError("expected missing inbox error")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_placeholder_blocks():
    root, inbox = make_workspace("placeholder")
    try:
        result = run("lite placeholder roster blocks", lite_cmd(root, inbox), expect_exit=1)
        if "placeholder_only" not in result.stderr:
            raise AssertionError("expected placeholder_only")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_incomplete_blocks():
    root, inbox = make_workspace("incomplete")
    try:
        result = run("lite incomplete roster blocks", lite_cmd(root, inbox), expect_exit=1)
        if "incomplete" not in result.stderr:
            raise AssertionError("expected incomplete")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_usable_cal1_allowed():
    root, inbox = make_workspace("usable")
    try:
        result = run("lite usable CAL-1 user-relay allowed", lite_cmd(root, inbox))
        if "You are LiteWorker." not in result.stdout:
            raise AssertionError("handoff missing worker identity")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_lite_user_relay_allowed_when_default_cal3_without_probe():
    root, inbox = make_workspace("usable", default_cal="CAL-3")
    try:
        result = run("lite user-relay allowed with default CAL-3", lite_cmd(root, inbox))
        if "You are LiteWorker." not in result.stdout:
            raise AssertionError("handoff missing worker identity")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    print("Running afc-lite.py fixture tests...")
    for test in [
        test_missing_blocks,
        test_placeholder_blocks,
        test_incomplete_blocks,
        test_usable_cal1_allowed,
        test_lite_user_relay_allowed_when_default_cal3_without_probe,
    ]:
        try:
            test()
        except Exception as exc:
            global FAIL
            FAIL += 1
            print("  [FAIL] {}: {}".format(test.__name__, exc))
    print()
    print("Results: {} passed, {} failed".format(PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
