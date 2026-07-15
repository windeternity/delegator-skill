#!/usr/bin/env python3
"""Fixture runner for CAL-3 probe, dispatcher, and release executor."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time


BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, "..", "..", ".."))
DISPATCH = os.path.join(ROOT, "scripts", "afc-cal3-dispatch.py")
PROBE = os.path.join(ROOT, "scripts", "afc-cal3-probe.py")
RELEASE = os.path.join(ROOT, "scripts", "afc-release-executor.py")
VALIDATOR = os.path.join(ROOT, "scripts", "validate-agent-inbox.py")
FAKE_WORKER = os.path.join(BASE, "fake_worker.py")

PASS = 0
FAIL = 0


def run(label, cmd, expect_exit=0, timeout=30, env=None):
    global PASS, FAIL
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    ok = result.returncode == expect_exit
    print("  [{}] {} (exit={}, expected={})".format(
        "PASS" if ok else "FAIL", label, result.returncode, expect_exit
    ))
    if ok:
        PASS += 1
    else:
        FAIL += 1
        print("    stdout: {}".format(result.stdout[:800]))
        print("    stderr: {}".format(result.stderr[:800]))
    return result


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def task_text(
    workspace,
    task_id="cal3-success",
    agent_name="FakeWorker",
    modify="no",
    run_commands="none",
    network_access="none",
    commit_push="no",
    destructive_actions="no",
    report_name=None,
    locked="README.md",
):
    report_name = report_name or "report-{}-{}.md".format(agent_name, task_id)
    return """---
schema: agent-file-coordination/task
schema_version: 0.1.0
task_id: {task_id}
agent_name: {agent_name}
role: implementer
protocol_mode: task-only
coordinator_authority: no
status: ASSIGNED
permission_scope:
  read_files: yes
  write_task_files: no
  write_reports: yes
  modify_source: {modify}
  run_commands: {run_commands}
  network_access: {network_access}
  commit_push: {commit_push}
  destructive_actions: {destructive_actions}
workspace:
  mode: existing_edit_worktree
  path: {workspace}
  may_create_worktree: no
  branch: main
  base: HEAD
  locked_files_or_areas: {locked}
validation_tier: no-test-needed
report_path: .agent-inbox/{report_name}
created_at: 2026-06-19
---
# Task - Fake Worker

## Role Boundary
You are the assigned worker, not the coordinator.
Do not create tasks, reassign work, approve final GO/PARTIAL/RED, or expand permission scope.
""".format(
        task_id=task_id,
        agent_name=agent_name,
        workspace=workspace.replace("\\", "/"),
        modify=modify,
        run_commands=run_commands,
        network_access=network_access,
        commit_push=commit_push,
        destructive_actions=destructive_actions,
        report_name=report_name,
        locked=locked,
    )


def write_cal3_roster(inbox, agent_name="FakeWorker"):
    write(os.path.join(inbox, "AGENT_ROSTER.md"), """---
schema: agent-file-coordination/roster
schema_version: 0.1.0
---
# Agent Roster

<!-- SESSION PREFERENCES
Default CAL: CAL-3
Execution preference: fixture CAL-3 worker
Available resources: probe-verified local fake worker
Available now: {agent_name}
Model preference order: fake
Avoid / unavailable: none
Smoke tests: fixture probe
Confirmed: 2026-06-29
Change policy: keep these defaults until the user asks to change them or a route becomes unavailable.
-->

| Agent Name | Role | Tool | Model | Provider / Access Path | Protocol Mode | Coordinator Authority | Can Edit | Can Run Commands | Can Write Reports | Browser / Visual | Worktree Capability | Best Use | Avoid | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Coordinator | coordinator | codex | coordinator-model | local coordinator | full-skill | yes | yes | bounded | yes | yes | can_use_existing | task decomposition, evidence review, final verdict | routine worker loops | fixture coordinator |
| {agent_name} | implementer | fake-cli | fake-model | local fake worker | task-only | no | yes | bounded | yes | no | can_use_existing | fixture CAL-3 work | none | external callable worker |
""".format(agent_name=agent_name))


def make_inbox(mode="success", task_id="cal3-success", agent_name="FakeWorker"):
    root = tempfile.mkdtemp(prefix="afc-cal3-")
    inbox = os.path.join(root, ".agent-inbox")
    os.makedirs(inbox, exist_ok=True)
    write(os.path.join(root, "README.md"), "# fixture\n")
    write(
        os.path.join(inbox, "task-{}-{}.md".format(agent_name, task_id)),
        task_text(root, task_id=task_id, agent_name=agent_name),
    )
    recipe = {
        "schema": "agent-file-coordination/cal3-invoke-recipes",
        "schema_version": "0.1.0",
        "default_permission_profile": "cal3-bounded-edit",
        "agent_recipes": {agent_name: "fake"},
        "probes": [{"tool": "fake", "available": True, "backend": "fixture"}],
        "recipes": {
            "fake": {
                "tool": "fake",
                "argv": [
                    sys.executable,
                    FAKE_WORKER,
                    "--task",
                    "{task_path}",
                    "--mode",
                    mode,
                ],
                "cwd": "{workspace}",
                "timeout_seconds": 3,
                "supports_resume": False,
                "capability": {
                    "modify_source": True,
                    "run_commands": "bounded",
                    "network_access": "none",
                    "commit_push": "no",
                },
                "approval_patterns": ["APPROVAL REQUIRED"],
                "profile_args": {
                    "cal3-readonly": {},
                    "cal3-bounded-edit": {},
                    "cal3-local-autonomous": {},
                    "cal3-local-autonomous-high": {},
                    "cal3-network-readonly": {},
                    "cal3-network-work": {},
                    "cal3-approved-commit": {},
                    "cal3-release-gated": {},
                },
            }
        },
    }
    write(os.path.join(inbox, "invoke-recipes.json"), json.dumps(recipe, indent=2))
    write_cal3_roster(inbox, agent_name=agent_name)
    return root, inbox


def init_git_repo(root, label_prefix):
    run("{}: git init".format(label_prefix), ["git", "-C", root, "init", "-b", "main"], timeout=10)
    run("{}: git config email".format(label_prefix), ["git", "-C", root, "config", "user.email", "fixture@example.com"])
    run("{}: git config name".format(label_prefix), ["git", "-C", root, "config", "user.name", "Fixture"])
    run("{}: initial add".format(label_prefix), ["git", "-C", root, "add", "README.md"])
    run("{}: initial commit".format(label_prefix), ["git", "-C", root, "commit", "-m", "test: initial"])


def test_probe_missing_inbox():
    run(
        "probe: missing inbox fails",
        [sys.executable, "-B", PROBE, "--inbox", os.path.join(tempfile.gettempdir(), "missing-afc-cal3-inbox")],
        expect_exit=1,
    )


def test_probe_codex_readonly_writes_report():
    root = tempfile.mkdtemp(prefix="afc-cal3-probe-")
    inbox = os.path.join(root, ".agent-inbox")
    bin_dir = os.path.join(root, "bin")
    os.makedirs(inbox, exist_ok=True)
    os.makedirs(bin_dir, exist_ok=True)
    if os.name == "nt":
        codex_path = os.path.join(bin_dir, "codex.cmd")
        write(
            codex_path,
            "@echo off\n"
            "if \"%1\"==\"--version\" echo codex-cli fake& exit /b 0\n"
            "if \"%1\"==\"exec\" if \"%2\"==\"--help\" echo Run Codex non-interactively& exit /b 0\n"
            "echo ok\n"
            "exit /b 0\n",
        )
    else:
        codex_path = os.path.join(bin_dir, "codex")
        write(
            codex_path,
            "#!/bin/sh\n"
            "if [ \"$1\" = \"--version\" ]; then echo 'codex-cli fake'; exit 0; fi\n"
            "if [ \"$1\" = \"exec\" ] && [ \"$2\" = \"--help\" ]; then echo 'Run Codex non-interactively'; exit 0; fi\n"
            "echo ok\n",
        )
        os.chmod(codex_path, 0o755)
    env = dict(os.environ)
    env["PATH"] = bin_dir + os.pathsep + env.get("PATH", "")
    env["AFC_CAL3_CODEX_EXE"] = codex_path
    # Ensure the native-backend path is exercised regardless of the outer env.
    env.pop("AFC_CAL3_CODEX_LAUNCHER", None)
    env.pop("AFC_CAL3_CODEX_NETWORK_ACCESS", None)
    if os.name == "nt":
        mimo_path = os.path.join(bin_dir, "mimo.cmd")
        claude_path = os.path.join(bin_dir, "claude.cmd")
        opencode_path = os.path.join(bin_dir, "opencode.cmd")
        write(
            mimo_path,
            "@echo off\n"
            "if \"%1\"==\"--version\" echo mimo fake& exit /b 0\n"
            "if \"%1\"==\"run\" if \"%2\"==\"--help\" echo Run Mimo non-interactively& exit /b 0\n"
            "echo ok\n"
            "exit /b 0\n",
        )
        write(
            claude_path,
            "@echo off\n"
            "if \"%1\"==\"--version\" echo claude fake& exit /b 0\n"
            "if \"%1\"==\"--help\" echo Claude help& exit /b 0\n"
            "echo ok\n"
            "exit /b 0\n",
        )
        write(
            opencode_path,
            "@echo off\n"
            "if \"%1\"==\"--version\" echo 1.17.8& exit /b 0\n"
            "if \"%1\"==\"run\" if \"%2\"==\"--help\" echo run opencode with a message& exit /b 0\n"
            "echo ok\n"
            "exit /b 0\n",
        )
    else:
        mimo_path = os.path.join(bin_dir, "mimo")
        claude_path = os.path.join(bin_dir, "claude")
        opencode_path = os.path.join(bin_dir, "opencode")
        write(
            mimo_path,
            "#!/bin/sh\n"
            "if [ \"$1\" = \"--version\" ]; then echo 'mimo fake'; exit 0; fi\n"
            "if [ \"$1\" = \"run\" ] && [ \"$2\" = \"--help\" ]; then echo 'Run Mimo non-interactively'; exit 0; fi\n"
            "echo ok\n",
        )
        write(
            claude_path,
            "#!/bin/sh\n"
            "if [ \"$1\" = \"--version\" ]; then echo 'claude fake'; exit 0; fi\n"
            "if [ \"$1\" = \"--help\" ]; then echo 'Claude help'; exit 0; fi\n"
            "echo ok\n",
        )
        write(
            opencode_path,
            "#!/bin/sh\n"
            "if [ \"$1\" = \"--version\" ]; then echo '1.17.8'; exit 0; fi\n"
            "if [ \"$1\" = \"run\" ] && [ \"$2\" = \"--help\" ]; then echo 'run opencode with a message'; exit 0; fi\n"
            "echo ok\n",
        )
        os.chmod(mimo_path, 0o755)
        os.chmod(claude_path, 0o755)
        os.chmod(opencode_path, 0o755)
    env["AFC_CAL3_OPENCODE_EXE"] = opencode_path
    try:
        run(
            "probe: codex readonly uses report-writable sandbox",
            [sys.executable, "-B", PROBE, "--inbox", inbox, "--write"],
            env=env,
        )
        recipe_path = os.path.join(inbox, "invoke-recipes.json")
        with open(recipe_path, "r", encoding="utf-8") as handle:
            recipe = json.load(handle)
        if recipe["recipes"]["codex"].get("sandbox") != "workspace-write":
            raise AssertionError("codex recipe should declare workspace-write sandbox")
        capability = recipe["recipes"]["codex"].get("capability") or {}
        if capability.get("network_access") != "none":
            raise AssertionError("codex recipe should not advertise network by default")
        env_allowed = dict(env)
        env_allowed["AFC_CAL3_CODEX_NETWORK_ACCESS"] = "allowed"
        run(
            "probe: codex network capability requires explicit opt-in",
            [sys.executable, "-B", PROBE, "--inbox", inbox, "--write"],
            env=env_allowed,
        )
        with open(recipe_path, "r", encoding="utf-8") as handle:
            recipe = json.load(handle)
        capability = recipe["recipes"]["codex"].get("capability") or {}
        if capability.get("network_access") != "allowed":
            raise AssertionError("codex network opt-in should declare capability allowed")
        sandbox = recipe["recipes"]["codex"]["profile_args"]["cal3-readonly"]["codex_sandbox"]
        if sandbox != "workspace-write":
            raise AssertionError("expected workspace-write, got {}".format(sandbox))
        patterns = recipe["recipes"]["codex"]["approval_patterns"]
        if "approval" in patterns:
            raise AssertionError("bare approval pattern causes false positives")
        codex_argv = recipe["recipes"]["codex"]["argv"]
        if os.path.abspath(codex_argv[0]) != os.path.abspath(codex_path):
            raise AssertionError("codex recipe should use resolved executable path")
        if "user_local_alias" in recipe["recipes"]:
            raise AssertionError("user-local aliases should not be generated by default")
        mimo = recipe["recipes"].get("mimo")
        if not mimo or "--dangerously-skip-permissions" not in mimo.get("argv", []):
            raise AssertionError("mimo recipe should include skip-permissions flag")
        if mimo.get("sandbox") != "none":
            raise AssertionError("mimo recipe should declare sandbox none")
        if "evidence_trust.level" not in " ".join(mimo.get("argv", [])):
            raise AssertionError("mimo recipe should include AFC report compatibility guidance")
        claude = recipe["recipes"].get("claude")
        if not claude:
            raise AssertionError("expected claude recipe")
        if claude.get("sandbox") != "none":
            raise AssertionError("claude recipe should declare sandbox none")
        if "--add-dir" in claude.get("argv", []):
            raise AssertionError("claude recipe should not use --add-dir")
        if claude.get("cwd") != "{workspace}":
            raise AssertionError("claude recipe should run from workspace cwd")
        opencode = recipe["recipes"].get("opencode")
        if not opencode:
            raise AssertionError("expected opencode recipe")
        if opencode.get("sandbox") != "none":
            raise AssertionError("opencode recipe should declare sandbox none")
        opencode_argv = opencode.get("argv", [])
        if os.path.abspath(opencode_argv[0]) != os.path.abspath(opencode_path):
            raise AssertionError("opencode recipe should use resolved executable path")
        if "--dangerously-skip-permissions" not in opencode_argv:
            raise AssertionError("opencode recipe should include skip-permissions flag")
        if opencode_argv[:4] != [opencode_path, "run", "--dir", "{workspace}"]:
            raise AssertionError("unexpected opencode argv shape: {}".format(opencode_argv))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_probe_codex_launcher():
    """AFC_CAL3_CODEX_LAUNCHER routes codex through the user's launcher script."""
    root = tempfile.mkdtemp(prefix="afc-cal3-launcher-")
    inbox = os.path.join(root, ".agent-inbox")
    os.makedirs(inbox, exist_ok=True)
    launcher = os.path.join(root, "codex3p-runner.ps1")
    write(launcher, "# fake launcher\n")
    env = dict(os.environ)
    env["AFC_CAL3_CODEX_LAUNCHER"] = launcher
    env["AFC_CAL3_CODEX_ALIASES"] = "reviewer3p, helper3p"
    env.pop("AFC_CAL3_CODEX_EXE", None)
    env.pop("AFC_CAL3_CODEX_NETWORK_ACCESS", None)
    try:
        run(
            "probe: codex launcher backend",
            [sys.executable, "-B", PROBE, "--inbox", inbox, "--write"],
            env=env,
        )
        with open(os.path.join(inbox, "invoke-recipes.json"), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        codex = data["recipes"]["codex"]
        if codex.get("backend") != "launcher":
            raise AssertionError("expected launcher backend, got {}".format(codex.get("backend")))
        capability = codex.get("capability") or {}
        if capability.get("network_access") != "none":
            raise AssertionError("launcher codex recipe should not advertise network by default")
        argv = codex["argv"]
        expected_prefix = [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", launcher,
        ]
        if argv[:6] != expected_prefix:
            raise AssertionError("unexpected launcher argv prefix: {}".format(argv[:6]))
        if "--skip-git-repo-check" not in argv or "exec" not in argv:
            raise AssertionError("launcher recipe should run codex exec with --skip-git-repo-check")
        probe = next((p for p in data["probes"] if p.get("tool") == "codex"), None)
        if not probe or probe.get("backend") != "launcher":
            raise AssertionError("codex probe should report launcher backend")
        aliases = data.get("agent_recipes") or {}
        for alias in ("codex3p", "reviewer3p", "helper3p"):
            if aliases.get(alias) != "codex":
                raise AssertionError("expected {} alias to map to codex, got {}".format(alias, aliases))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_probe_codex_launcher_missing_fails_closed():
    """A missing configured launcher must not fall back to native codex."""
    root = tempfile.mkdtemp(prefix="afc-cal3-launcher-missing-")
    inbox = os.path.join(root, ".agent-inbox")
    os.makedirs(inbox, exist_ok=True)
    missing_launcher = os.path.join(root, "missing-codex3p-runner.ps1")
    native_codex = os.path.join(root, "codex.cmd" if os.name == "nt" else "codex")
    if os.name == "nt":
        write(
            native_codex,
            "@echo off\n"
            "if \"%1\"==\"--version\" echo codex-cli fake& exit /b 0\n"
            "if \"%1\"==\"exec\" if \"%2\"==\"--help\" echo Run Codex non-interactively& exit /b 0\n"
            "exit /b 0\n",
        )
    else:
        write(
            native_codex,
            "#!/bin/sh\n"
            "if [ \"$1\" = \"--version\" ]; then echo 'codex-cli fake'; exit 0; fi\n"
            "if [ \"$1\" = \"exec\" ] && [ \"$2\" = \"--help\" ]; then echo 'Run Codex non-interactively'; exit 0; fi\n"
        )
        os.chmod(native_codex, 0o755)
    env = dict(os.environ)
    env["AFC_CAL3_CODEX_LAUNCHER"] = missing_launcher
    env["AFC_CAL3_CODEX_EXE"] = native_codex
    env.pop("AFC_CAL3_CODEX_NETWORK_ACCESS", None)
    try:
        run(
            "probe: missing codex launcher fails closed",
            [sys.executable, "-B", PROBE, "--inbox", inbox, "--write"],
            env=env,
        )
        with open(os.path.join(inbox, "invoke-recipes.json"), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if "codex" in data.get("recipes", {}):
            raise AssertionError("missing launcher must not generate a native codex recipe")
        probe = next((p for p in data["probes"] if p.get("tool") == "codex"), None)
        if not probe or probe.get("available") is not False or probe.get("backend") != "launcher":
            raise AssertionError("codex probe should report unavailable launcher backend")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_timeout_kills_process_tree():
    root, inbox = make_inbox("spawn-child-sleep", task_id="cal3-timeout-tree")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "30"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: timeout kills worker process tree",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-timeout-tree",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "1",
                "--json",
            ],
            expect_exit=1,
            timeout=15,
        )
        status = read_status(inbox, "cal3-timeout-tree")
        if status.get("state") != "TIMEOUT":
            raise AssertionError("expected TIMEOUT, got {}".format(status))
        termination = status.get("timeout_termination") or {}
        if termination.get("attempted") is not True:
            raise AssertionError("expected timeout termination attempt, got {}".format(status))
        pid_path = os.path.join(root, "child.pid")
        if not os.path.isfile(pid_path):
            raise AssertionError("expected child pid file")
        with open(pid_path, "r", encoding="utf-8") as handle:
            child_pid = int(handle.read().strip())
        if not wait_pid_exit(child_pid, timeout=8):
            raise AssertionError("child process still running after timeout: {}".format(child_pid))

        events = read_events(inbox)
        timeout_event = next(
            (
                event for event in events
                if event.get("event_type") == "TASK_ABORTED"
                and event.get("abort_reason") == "timeout"
            ),
            None,
        )
        if not timeout_event or timeout_event.get("attempt") != 1:
            raise AssertionError("timeout event missing attempt history: {}".format(events))

        # Retry the same task successfully. The mutable status may advance to
        # FINISHED, but append-only history must retain attempt 1's timeout.
        with open(recipe_path, "r", encoding="utf-8") as handle:
            retry_recipe = json.load(handle)
        argv = retry_recipe["recipes"]["fake"]["argv"]
        mode_index = argv.index("--mode") + 1
        argv[mode_index] = "success"
        retry_recipe["recipes"]["fake"]["argv"] = argv[:-2]
        write(recipe_path, json.dumps(retry_recipe, indent=2))
        run(
            "dispatch: timeout retry succeeds with retained history",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-timeout-tree",
                "--watch-max-iterations",
                "5",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "5",
                "--max-attempts",
                "2",
                "--json",
            ],
        )
        events = read_events(inbox)
        attempts = [
            event.get("attempt") for event in events
            if event.get("event_type") == "TASK_STARTED"
        ]
        if attempts != [1, 2]:
            raise AssertionError("expected retained attempts [1, 2], got {}".format(attempts))
        if not any(
            event.get("event_type") == "TASK_ABORTED"
            and event.get("abort_reason") == "timeout"
            and event.get("attempt") == 1
            for event in events
        ):
            raise AssertionError("retry lost timeout history: {}".format(events))
        assert_canonical_inbox_valid(inbox)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_timeout_records_source_residue():
    root, inbox = make_inbox("stray-source-sleep", task_id="cal3-timeout-source-residue")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "30"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: timeout records source residue",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-timeout-source-residue",
                "--permission-profile",
                "cal3-readonly",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "1",
                "--json",
            ],
            expect_exit=1,
            timeout=15,
        )
        status = read_status(inbox, "cal3-timeout-source-residue")
        if status.get("state") != "TIMEOUT":
            raise AssertionError("expected TIMEOUT, got {}".format(status))
        if "STRAY.md" not in status.get("source_violations", []):
            raise AssertionError("expected timeout source residue, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_timeout_records_commit_residue():
    root, inbox = make_inbox("commit-source-sleep", task_id="cal3-timeout-commit-residue")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "30"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        init_git_repo(root, "timeout commit residue")
        run(
            "dispatch: timeout records commit residue",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-timeout-commit-residue",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "1",
                "--json",
            ],
            expect_exit=1,
            timeout=15,
        )
        status = read_status(inbox, "cal3-timeout-commit-residue")
        if status.get("state") != "TIMEOUT":
            raise AssertionError("expected TIMEOUT, got {}".format(status))
        if not status.get("commit_violations"):
            raise AssertionError("expected timeout commit residue, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def read_events(inbox):
    events_path = os.path.join(inbox, "events.jsonl")
    events = []
    if not os.path.isfile(events_path):
        return events
    with open(events_path, "r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def assert_canonical_inbox_valid(inbox):
    result = subprocess.run(
        [sys.executable, "-B", VALIDATOR, "--active-only", inbox],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise AssertionError(
            "canonical inbox validation failed:\n{}\n{}".format(
                result.stdout, result.stderr
            )
        )


def test_cal3_event_metadata_validation():
    global PASS
    root, inbox = make_inbox("success", task_id="cal3-event-contract")
    events_path = os.path.join(inbox, "events.jsonl")
    base = {
        "schema": "agent-file-coordination/event",
        "schema_version": "0.1.0",
        "event_id": "evt-cal3-event-contract-heartbeat",
        "event_type": "WORKER_HEARTBEAT",
        "task_id": "cal3-event-contract",
        "created_at": "2026-07-11",
        "summary": "heartbeat",
    }
    try:
        write(events_path, json.dumps(base) + "\n")
        result = subprocess.run(
            [sys.executable, "-B", VALIDATOR, "--active-only", inbox],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 or "positive integer attempt" not in result.stdout:
            raise AssertionError("missing attempt unexpectedly validated: {}".format(result.stdout))

        aborted = dict(base)
        aborted.update({
            "event_id": "evt-cal3-event-contract-aborted",
            "event_type": "TASK_ABORTED",
            "attempt": 1,
            "worker_session_id": "pid:123",
        })
        write(events_path, json.dumps(aborted) + "\n")
        result = subprocess.run(
            [sys.executable, "-B", VALIDATOR, "--active-only", inbox],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 or "abort_reason is required" not in result.stdout:
            raise AssertionError("missing abort_reason unexpectedly validated: {}".format(result.stdout))
        PASS += 1
        print("  [PASS] CAL-3 event metadata validator rejects malformed variants")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_heartbeat_is_liveness_not_completion():
    root, inbox = make_inbox("stderr-sleep", task_id="cal3-heartbeat")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "1.2"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: heartbeat is liveness not completion",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-heartbeat",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "5",
                "--heartbeat-interval-seconds",
                "0.2",
                "--json",
            ],
            expect_exit=1,
            timeout=10,
        )
        events = read_events(inbox)
        if not any(event.get("event_type") == "WORKER_HEARTBEAT" for event in events):
            raise AssertionError("expected WORKER_HEARTBEAT event")
        status = read_status(inbox, "cal3-heartbeat")
        if status.get("state") != "NO_REPORT":
            raise AssertionError("heartbeat must not count as completion evidence: {}".format(status))
        if not status.get("primary_log_path", "").endswith("stderr.log"):
            raise AssertionError("expected stderr primary log, got {}".format(status))
        if "worker trace on stderr" not in status.get("redacted_primary_log_tail", ""):
            raise AssertionError("expected stderr primary tail, got {}".format(status))
        if not os.path.isfile(os.path.join(inbox, "artifacts", "cal3", "cal3-heartbeat", "LOGS.md")):
            raise AssertionError("expected CAL-3 log README")
        heartbeat = next(
            event for event in events if event.get("event_type") == "WORKER_HEARTBEAT"
        )
        if heartbeat.get("attempt") != 1 or not heartbeat.get("worker_session_id"):
            raise AssertionError("heartbeat missing attempt/session identity: {}".format(heartbeat))
        assert_canonical_inbox_valid(inbox)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_no_progress_abort_kills_worker():
    root, inbox = make_inbox("spawn-child-sleep", task_id="cal3-no-progress-abort")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "30"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: no-progress abort kills worker",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-no-progress-abort",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "20",
                "--abort-on-no-progress-seconds",
                "0.5",
                "--json",
            ],
            expect_exit=1,
            timeout=15,
        )
        status = read_status(inbox, "cal3-no-progress-abort")
        if status.get("state") != "ABORTED" or status.get("abort_reason") != "no_progress":
            raise AssertionError("expected no_progress abort, got {}".format(status))
        if not (status.get("abort_termination") or {}).get("attempted"):
            raise AssertionError("expected abort termination details, got {}".format(status))
        events = read_events(inbox)
        aborted = next(
            (event for event in events if event.get("event_type") == "TASK_ABORTED"),
            None,
        )
        if not aborted:
            raise AssertionError("expected TASK_ABORTED event")
        if aborted.get("attempt") != 1 or not aborted.get("worker_session_id"):
            raise AssertionError("abort missing attempt/session identity: {}".format(aborted))
        assert_canonical_inbox_valid(inbox)
        pid_path = os.path.join(root, "child.pid")
        if os.path.isfile(pid_path):
            with open(pid_path, "r", encoding="utf-8") as handle:
                child_pid = int(handle.read().strip())
            if not wait_pid_exit(child_pid, timeout=8):
                raise AssertionError("child process still running after no-progress abort: {}".format(child_pid))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_no_progress_abort_records_source_residue():
    root, inbox = make_inbox("stray-source-sleep", task_id="cal3-abort-source-residue")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "30"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: aborted readonly worker records source residue",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-abort-source-residue",
                "--permission-profile",
                "cal3-readonly",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "20",
                "--abort-on-no-progress-seconds",
                "0.5",
                "--json",
            ],
            expect_exit=1,
            timeout=15,
        )
        status = read_status(inbox, "cal3-abort-source-residue")
        if status.get("state") != "ABORTED" or status.get("abort_reason") != "no_progress":
            raise AssertionError("expected no_progress abort, got {}".format(status))
        if "STRAY.md" not in status.get("source_violations", []):
            raise AssertionError("expected aborted source residue, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_no_progress_abort_records_commit_residue():
    root, inbox = make_inbox("commit-source-sleep", task_id="cal3-abort-commit-residue")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "30"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        init_git_repo(root, "abort commit residue")
        run(
            "dispatch: aborted worker records commit residue",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-abort-commit-residue",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "20",
                "--abort-on-no-progress-seconds",
                "0.5",
                "--json",
            ],
            expect_exit=1,
            timeout=15,
        )
        status = read_status(inbox, "cal3-abort-commit-residue")
        if status.get("state") != "ABORTED" or status.get("abort_reason") != "no_progress":
            raise AssertionError("expected no_progress abort, got {}".format(status))
        if not status.get("commit_violations"):
            raise AssertionError("expected aborted commit residue, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_no_progress_abort_promotes_approval_required():
    root, inbox = make_inbox("approval-sleep", task_id="cal3-abort-approval-required")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "30"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: aborted approval prompt requires manual action",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-abort-approval-required",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "20",
                "--abort-on-no-progress-seconds",
                "0.5",
                "--json",
            ],
            expect_exit=2,
            timeout=15,
        )
        status = read_status(inbox, "cal3-abort-approval-required")
        if status.get("state") != "APPROVAL_REQUIRED":
            raise AssertionError("expected approval promotion, got {}".format(status))
        if status.get("abort_reason") != "no_progress":
            raise AssertionError("expected retained abort metadata, got {}".format(status))
        if "APPROVAL REQUIRED" not in status.get("redacted_primary_log_tail", ""):
            raise AssertionError("expected approval evidence tail, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_no_progress_does_not_abort_completed_worker():
    root, inbox = make_inbox("delayed-success", task_id="cal3-no-progress-race-success")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "0.45"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: no-progress does not abort completed worker",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-no-progress-race-success",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "5",
                "--abort-on-no-progress-seconds",
                "0.5",
                "--json",
            ],
            timeout=10,
        )
        status = read_status(inbox, "cal3-no-progress-race-success")
        if status.get("state") != "FINISHED":
            raise AssertionError("completed worker should not be aborted: {}".format(status))
        report_validation = status.get("report_validation") or {}
        if report_validation.get("result") != "pass":
            raise AssertionError("expected valid report, got {}".format(status))
        if status.get("abort_reason"):
            raise AssertionError("unexpected abort fields on completed worker: {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_repeated_failure_abort():
    root, inbox = make_inbox("http-failures", task_id="cal3-repeated-failure-abort")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "1.5"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: repeated HTTP failures abort worker",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-repeated-failure-abort",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "10",
                "--abort-on-repeated-failures",
                "2",
                "--json",
            ],
            expect_exit=1,
            timeout=10,
        )
        status = read_status(inbox, "cal3-repeated-failure-abort")
        if status.get("state") != "ABORTED" or status.get("abort_reason") != "repeated_failures":
            raise AssertionError("expected repeated_failures abort, got {}".format(status))
        if "404" not in status.get("abort_evidence_tail", ""):
            raise AssertionError("expected failure evidence tail, got {}".format(status))
        events = read_events(inbox)
        aborted = [event for event in events if event.get("event_type") == "TASK_ABORTED"]
        if not aborted or aborted[-1].get("abort_reason") != "repeated_failures":
            raise AssertionError("expected repeated failure TASK_ABORTED event, got {}".format(events))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_repeated_failure_abort_from_stdout():
    root, inbox = make_inbox("http-failures-stdout", task_id="cal3-repeated-failure-stdout")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "1.5"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: repeated HTTP failures on stdout abort worker",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-repeated-failure-stdout",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "10",
                "--abort-on-repeated-failures",
                "2",
                "--json",
            ],
            expect_exit=1,
            timeout=10,
        )
        status = read_status(inbox, "cal3-repeated-failure-stdout")
        if status.get("state") != "ABORTED" or status.get("abort_reason") != "repeated_failures":
            raise AssertionError("expected repeated_failures abort, got {}".format(status))
        if "stdout:" not in status.get("abort_evidence_tail", ""):
            raise AssertionError("expected stdout evidence section, got {}".format(status))
        if "404" not in status.get("abort_evidence_tail", ""):
            raise AssertionError("expected stdout failure evidence, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_success():
    root, inbox = make_inbox("success")
    try:
        result = run(
            "dispatch: success writes report",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-success",
                "--watch-max-iterations",
                "5",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
        )
        report = os.path.join(inbox, "report-FakeWorker-cal3-success.md")
        if not os.path.isfile(report):
            raise AssertionError("report not written")
        run("dispatch: generated inbox validates", [sys.executable, "-B", VALIDATOR, inbox])
        if '"state": "started"' not in result.stdout and '"state":"started"' not in result.stdout:
            raise AssertionError("missing started status")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_missing_probe_blocks_automatic_dispatch():
    root, inbox = make_inbox("success", task_id="cal3-missing-probe")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe.pop("probes", None)
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        result = run(
            "dispatch: missing CAL-3 probe blocks automatic dispatch",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-missing-probe",
                "--dry-run",
                "--json",
            ],
            expect_exit=2,
        )
        if "ROSTER_BLOCKED" not in result.stderr or "CAL-3 requires" not in result.stderr:
            raise AssertionError("expected CAL-3 roster block, got {}".format(result.stderr[:400]))
        if os.path.isdir(os.path.join(inbox, "artifacts", "cal3", "cal3-missing-probe")):
            raise AssertionError("worker artifacts should not be created when probe is missing")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_report_path_outside_workspace():
    root = tempfile.mkdtemp(prefix="afc-cal3-outside-")
    workspace = os.path.join(root, "workspace")
    inbox = os.path.join(root, "inbox")
    os.makedirs(workspace, exist_ok=True)
    os.makedirs(inbox, exist_ok=True)
    write(
        os.path.join(inbox, "task-FakeWorker-cal3-outside-report.md"),
        task_text(workspace, task_id="cal3-outside-report"),
    )
    recipe = {
        "schema": "agent-file-coordination/cal3-invoke-recipes",
        "schema_version": "0.1.0",
        "default_permission_profile": "cal3-bounded-edit",
        "agent_recipes": {"FakeWorker": "fake"},
        "probes": [{"tool": "codex", "available": True, "backend": "fixture"}],
        "recipes": {
            "fake": {
                "tool": "codex",
                "argv": [sys.executable, FAKE_WORKER, "--task", "{task_path}", "--mode", "success"],
                "cwd": "{workspace}",
                "timeout_seconds": 3,
                "supports_resume": False,
                "capability": {
                    "modify_source": True,
                    "run_commands": "bounded",
                    "network_access": "none",
                    "commit_push": "no",
                },
                "approval_patterns": ["APPROVAL REQUIRED"],
                "profile_args": {
                    "cal3-bounded-edit": {"codex_sandbox": "workspace-write"},
                    "cal3-local-autonomous-high": {"codex_sandbox": "workspace-write"},
                },
            }
        },
    }
    write(os.path.join(inbox, "invoke-recipes.json"), json.dumps(recipe, indent=2))
    write_cal3_roster(inbox)
    try:
        result = run(
            "dispatch: report path outside workspace fails fast",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-outside-report",
                "--dry-run",
                "--json",
            ],
            expect_exit=2,
        )
        if "report_path_outside_workspace" not in result.stdout:
            raise AssertionError("expected report_path_outside_workspace, got {}".format(result.stdout))
        if os.path.isdir(os.path.join(inbox, "artifacts", "cal3", "cal3-outside-report")):
            raise AssertionError("worker artifacts should not be created before fail-fast")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_process_exit_validates_report_before_watcher():
    root, inbox = make_inbox("delayed-success", task_id="cal3-direct-report")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].extend(["--sleep", "2"])
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        result = run(
            "dispatch: process exit validates report before watcher",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-direct-report",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "5",
                "--json",
            ],
        )
        status_path = os.path.join(inbox, "artifacts", "cal3", "cal3-direct-report", "status.json")
        with open(status_path, "r", encoding="utf-8") as handle:
            status = json.load(handle)
        if status.get("state") != "FINISHED":
            raise AssertionError("expected FINISHED, got {}".format(status))
        direct = status.get("report_validation") or {}
        if direct.get("result") != "pass":
            raise AssertionError("expected direct validation pass, got {}".format(direct))
        watch = status.get("watch_event") or {}
        if watch.get("event") != "report_ready":
            raise AssertionError("expected compat watcher report_ready, got {}".format(watch))
        if "watch_compat_armed" not in result.stdout:
            raise AssertionError("expected watcher to run only as compatibility path")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def read_status(inbox, task_id):
    status_path = os.path.join(inbox, "artifacts", "cal3", task_id, "status.json")
    with open(status_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def update_fake_capability(inbox, **capability):
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["capability"].update(capability)
    write(recipe_path, json.dumps(recipe, indent=2))


def pid_running(pid):
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "PID eq {}".format(pid), "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return str(pid) in (result.stdout or "")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    proc_stat = "/proc/{}/stat".format(pid)
    if os.path.isfile(proc_stat):
        try:
            with open(proc_stat, "r", encoding="utf-8", errors="replace") as handle:
                parts = handle.read().split()
            if len(parts) > 2 and parts[2] == "Z":
                return False
        except OSError:
            return False
    else:
        try:
            result = subprocess.run(
                ["ps", "-o", "stat=", "-p", str(pid)],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            result = None
        if result is not None and result.returncode == 0:
            stat = (result.stdout or "").strip()
            if stat.startswith("Z"):
                return False
    return True


def wait_pid_exit(pid, timeout=5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not pid_running(pid):
            return True
        time.sleep(0.1)
    return not pid_running(pid)


def test_dispatch_readonly_report_only_passes():
    root, inbox = make_inbox("success", task_id="cal3-readonly-report-only")
    try:
        run(
            "dispatch: readonly report write is allowed",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-readonly-report-only",
                "--permission-profile",
                "cal3-readonly",
                "--watch-max-iterations",
                "5",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
        )
        status = read_status(inbox, "cal3-readonly-report-only")
        if status.get("state") != "FINISHED":
            raise AssertionError("expected readonly pass, got {}".format(status))
        if status.get("source_violations"):
            raise AssertionError("report-only readonly task should not violate source guard")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_readonly_source_violation():
    root, inbox = make_inbox("stray-source", task_id="cal3-source-violation")
    try:
        run(
            "dispatch: readonly source violation fails",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-source-violation",
                "--permission-profile",
                "cal3-readonly",
                "--watch-max-iterations",
                "5",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
            expect_exit=1,
        )
        status = read_status(inbox, "cal3-source-violation")
        if status.get("state") != "SOURCE_VIOLATION":
            raise AssertionError("expected SOURCE_VIOLATION, got {}".format(status))
        if "STRAY.md" not in status.get("source_violations", []):
            raise AssertionError("expected STRAY.md violation, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_readonly_source_residue_recorded_on_failed_exit():
    root, inbox = make_inbox("stray-source-fail", task_id="cal3-source-residue-fail")
    try:
        run(
            "dispatch: failed readonly worker still records source residue",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-source-residue-fail",
                "--permission-profile",
                "cal3-readonly",
                "--watch-max-iterations",
                "5",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
            expect_exit=1,
        )
        status = read_status(inbox, "cal3-source-residue-fail")
        if status.get("state") != "FAILED":
            raise AssertionError("expected FAILED state preserved, got {}".format(status))
        if "STRAY.md" not in status.get("source_violations", []):
            raise AssertionError("expected STRAY.md recorded as residue, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_readonly_predirty_file_reedit_violation():
    root, inbox = make_inbox("edit-readme", task_id="cal3-predirty-source-violation")
    try:
        init_git_repo(root, "dispatch predirty")
        write(os.path.join(root, "README.md"), "# fixture\npre dirty\n")
        run(
            "dispatch: readonly catches re-edit of pre-dirty file",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-predirty-source-violation",
                "--permission-profile",
                "cal3-readonly",
                "--watch-max-iterations",
                "5",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
            expect_exit=1,
        )
        status = read_status(inbox, "cal3-predirty-source-violation")
        if status.get("state") != "SOURCE_VIOLATION":
            raise AssertionError("expected SOURCE_VIOLATION, got {}".format(status))
        if "README.md" not in status.get("source_violations", []):
            raise AssertionError("expected README.md violation, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_commit_violation():
    root, inbox = make_inbox("commit-source", task_id="cal3-commit-violation")
    try:
        init_git_repo(root, "dispatch commit violation")
        run(
            "dispatch: non-release profile catches worker commit",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-commit-violation",
                "--permission-profile",
                "cal3-readonly",
                "--watch-max-iterations",
                "5",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "5",
                "--json",
            ],
            expect_exit=1,
        )
        status = read_status(inbox, "cal3-commit-violation")
        if status.get("state") != "COMMIT_VIOLATION":
            raise AssertionError("expected COMMIT_VIOLATION, got {}".format(status))
        if not status.get("commit_violations"):
            raise AssertionError("expected commit violation details, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_invalid_report_state():
    root, inbox = make_inbox("invalid-report", task_id="cal3-invalid-report")
    try:
        run(
            "dispatch: invalid report is distinct from no report",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-invalid-report",
                "--watch-max-iterations",
                "5",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
            expect_exit=1,
        )
        status = read_status(inbox, "cal3-invalid-report")
        if status.get("state") != "INVALID_REPORT":
            raise AssertionError("expected INVALID_REPORT, got {}".format(status))
        direct = status.get("report_validation") or {}
        if direct.get("result") != "fail":
            raise AssertionError("expected direct validation fail, got {}".format(direct))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_guardrail_yes_is_invalid():
    root, inbox = make_inbox("guardrail-yes", task_id="cal3-guardrail-yes")
    try:
        run(
            "dispatch: guardrail yes is invalid",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-guardrail-yes",
                "--watch-max-iterations",
                "5",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
            expect_exit=1,
        )
        status = read_status(inbox, "cal3-guardrail-yes")
        if status.get("state") != "INVALID_REPORT":
            raise AssertionError("expected INVALID_REPORT, got {}".format(status))
        direct = status.get("report_validation") or {}
        if "permission_scope_expanded" not in str(direct.get("reason", "")):
            raise AssertionError("expected permission_scope_expanded rejection, got {}".format(direct))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_report_agent_name_mismatch_is_invalid():
    # A report whose agent_name disagrees with its task must be rejected at
    # dispatch intake (INVALID_REPORT), not deferred to the intake stage.
    # This exercises the task= cross-check added to validate_expected_report;
    # the report is otherwise schema-valid, so only the agent_name mismatch
    # can fail it.
    root, inbox = make_inbox("wrong-agent", task_id="cal3-wrong-agent")
    try:
        run(
            "dispatch: report agent_name mismatch is invalid at dispatch",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-wrong-agent",
                "--watch-max-iterations",
                "5",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
            expect_exit=1,
        )
        status = read_status(inbox, "cal3-wrong-agent")
        if status.get("state") != "INVALID_REPORT":
            raise AssertionError("expected INVALID_REPORT, got {}".format(status))
        direct = status.get("report_validation") or {}
        if "agent_name" not in str(direct.get("reason", "")):
            raise AssertionError("expected agent_name mismatch rejection, got {}".format(direct))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_readonly_changed_files_is_invalid():
    # Default task is modify_source=no (read-only). A report that lists real
    # changed_files must be rejected at dispatch via the modify_source
    # cross-check. This needs the flat dispatch task's permission_scope.*
    # dotted keys nested for validate_report_schema to see them.
    root, inbox = make_inbox("changed-files", task_id="cal3-changed-files")
    try:
        run(
            "dispatch: read-only task + changed_files is invalid at dispatch",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-changed-files",
                "--watch-max-iterations",
                "5",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
            expect_exit=1,
        )
        status = read_status(inbox, "cal3-changed-files")
        if status.get("state") != "INVALID_REPORT":
            raise AssertionError("expected INVALID_REPORT, got {}".format(status))
        direct = status.get("report_validation") or {}
        reason = str(direct.get("reason", ""))
        if "modify_source" not in reason and "changed_files" not in reason:
            raise AssertionError("expected modify_source/changed_files rejection, got {}".format(direct))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_prompt_includes_coordination_metadata():
    global PASS
    # A task carrying coordination_mode / comparison_group must surface them
    # in the worker prompt's report template; otherwise a hand-writing worker
    # would omit them and trip the dispatch-time task cross-check on
    # coordinated CAL-3 tasks.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "afc_cal3_dispatch_prompt", os.path.join(ROOT, "scripts", "afc-cal3-dispatch.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    p_with = mod.prompt_for_task(
        {"task_id": "t1", "agent_name": "FakeWorker",
         "coordination_mode": "delegate_full", "comparison_group": "group-1"},
        "/ws", "/ws/task.md", "/ws/report.md",
    )
    if "coordination_mode: delegate_full" not in p_with or "comparison_group: group-1" not in p_with:
        raise AssertionError("prompt omitted coordination metadata:\n{}".format(p_with))

    p_without = mod.prompt_for_task(
        {"task_id": "t1", "agent_name": "FakeWorker"},
        "/ws", "/ws/task.md", "/ws/report.md",
    )
    if "coordination_mode" in p_without or "comparison_group" in p_without:
        raise AssertionError("prompt mentioned coordination metadata when task has none:\n{}".format(p_without))
    PASS += 1
    print("  [PASS] prompt includes coordination metadata only when task carries it")


def test_dispatch_dry_run_does_not_write_events():
    root, inbox = make_inbox("success", task_id="cal3-dry-run")
    try:
        run(
            "dispatch: dry-run does not write dispatch event",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-dry-run",
                "--dry-run",
                "--json",
            ],
        )
        events_path = os.path.join(inbox, "events.jsonl")
        if os.path.exists(events_path):
            with open(events_path, "r", encoding="utf-8") as handle:
                if "TASK_DISPATCHED" in handle.read():
                    raise AssertionError("dry-run wrote TASK_DISPATCHED")
        status = read_status(inbox, "cal3-dry-run")
        if status.get("state") != "DRY_RUN":
            raise AssertionError("expected DRY_RUN status, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_dry_run_records_env_keys_only():
    root, inbox = make_inbox("success", task_id="cal3-env-dry-run")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["env"] = {
        "AFC_FIXTURE_ENV": "visible-key-only",
        "SECRET_TOKEN": "should-not-appear-in-status",
    }
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: dry-run status records env keys only",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-env-dry-run",
                "--dry-run",
                "--json",
            ],
        )
        status = read_status(inbox, "cal3-env-dry-run")
        if status.get("env_keys") != ["AFC_FIXTURE_ENV", "SECRET_TOKEN"]:
            raise AssertionError("expected env keys only, got {}".format(status))
        if "should-not-appear-in-status" in json.dumps(status):
            raise AssertionError("env value leaked into dry-run status")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_status_labels_worktree_as_cwd():
    root, inbox = make_inbox("success", task_id="cal3-cwd-label")
    try:
        result = run(
            "dispatch: status labels assigned worktree as cwd",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-cwd-label",
                "--dry-run",
                "--json",
            ],
        )
        status = read_status(inbox, "cal3-cwd-label")
        cwd = status.get("cwd")
        if not cwd:
            raise AssertionError("dry-run status missing cwd label")
        if os.path.normcase(os.path.normpath(cwd)) != os.path.normcase(os.path.normpath(root)):
            raise AssertionError("cwd is not the assigned worktree: {}".format(cwd))
        script_dir = os.path.dirname(DISPATCH)
        if os.path.normcase(os.path.normpath(cwd)) == os.path.normcase(os.path.normpath(script_dir)):
            raise AssertionError("cwd must not be the dispatcher script directory")
        dispatch_payload = None
        for raw in result.stdout.splitlines():
            raw = raw.strip()
            if not raw.startswith("{"):
                continue
            payload = json.loads(raw)
            if payload.get("state") == "dispatch":
                dispatch_payload = payload
                break
        if not dispatch_payload:
            raise AssertionError("dispatch status line not emitted")
        line_cwd = dispatch_payload.get("cwd")
        if not line_cwd or os.path.normcase(os.path.normpath(line_cwd)) != os.path.normcase(os.path.normpath(root)):
            raise AssertionError("dispatch line did not label worktree as cwd: {}".format(line_cwd))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_stdin_approval_does_not_hang():
    root, inbox = make_inbox("stdin-approval", task_id="cal3-stdin-approval")
    try:
        run(
            "dispatch: stdin approval gets EOF",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-stdin-approval",
                "--watch-max-iterations",
                "2",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
            expect_exit=2,
            timeout=10,
        )
        status = read_status(inbox, "cal3-stdin-approval")
        if status.get("state") != "APPROVAL_REQUIRED":
            raise AssertionError("expected APPROVAL_REQUIRED, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_prompt_contains_report_template():
    root, inbox = make_inbox("success", task_id="cal3-prompt-template")
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["argv"].append("{prompt}")
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: prompt includes schema-valid report template",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-prompt-template",
                "--dry-run",
                "--json",
            ],
        )
        status = read_status(inbox, "cal3-prompt-template")
        prompt = status.get("argv", [])[-1]
        required = [
            "schema: agent-file-coordination/report",
            "evidence_trust:",
            "guardrails:",
            "validation:",
            "trust_level: referenced",
            "role_boundary_followed: yes",
        ]
        missing = [item for item in required if item not in prompt]
        if missing:
            raise AssertionError("prompt template missing {}".format(missing))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_no_report():
    root, inbox = make_inbox("no-report", task_id="cal3-no-report")
    try:
        run(
            "dispatch: no report fails closed",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-no-report",
                "--watch-max-iterations",
                "2",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
            expect_exit=1,
        )
        status_path = os.path.join(inbox, "artifacts", "cal3", "cal3-no-report", "status.json")
        with open(status_path, "r", encoding="utf-8") as handle:
            status = json.load(handle)
        if status.get("state") != "NO_REPORT":
            raise AssertionError("expected NO_REPORT, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_approval_required():
    root, inbox = make_inbox("approval", task_id="cal3-approval")
    try:
        run(
            "dispatch: approval required",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-approval",
                "--watch-max-iterations",
                "2",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
            expect_exit=2,
        )
        status_path = os.path.join(inbox, "artifacts", "cal3", "cal3-approval", "status.json")
        with open(status_path, "r", encoding="utf-8") as handle:
            status = json.load(handle)
        if status.get("state") != "APPROVAL_REQUIRED":
            raise AssertionError("expected APPROVAL_REQUIRED, got {}".format(status))
        if "APPROVAL REQUIRED" not in status.get("redacted_stdout_tail", ""):
            raise AssertionError("expected redacted stdout tail")
        if "secret-value" in status.get("redacted_stdout_tail", ""):
            raise AssertionError("secret value was not redacted")
        if "abcdefghijklmnopqrstuvwxyz" in status.get("redacted_stdout_tail", ""):
            raise AssertionError("sk-style token was not redacted")
        if "task-mimo-readonly.md" not in status.get("redacted_stdout_tail", ""):
            raise AssertionError("task path was falsely redacted as sk-style token")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_permission_profile_blocks_write():
    root, inbox = make_inbox("success", task_id="cal3-readonly-block")
    task_path = os.path.join(inbox, "task-FakeWorker-cal3-readonly-block.md")
    write(task_path, task_text(root, task_id="cal3-readonly-block", modify="yes", run_commands="none"))
    try:
        run(
            "dispatch: readonly profile blocks modify_source",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-readonly-block",
                "--permission-profile",
                "cal3-readonly",
            ],
            expect_exit=1,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_local_autonomous_high_allows_bounded_local_work():
    root, inbox = make_inbox("success", task_id="cal3-local-high")
    task_path = os.path.join(inbox, "task-FakeWorker-cal3-local-high.md")
    write(task_path, task_text(root, task_id="cal3-local-high", modify="yes", run_commands="bounded"))
    try:
        run(
            "dispatch: local autonomous high allows bounded local work",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-local-high",
                "--permission-profile",
                "cal3-local-autonomous-high",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
        )
        status = read_status(inbox, "cal3-local-high")
        if status.get("state") != "FINISHED":
            raise AssertionError("expected FINISHED, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_local_autonomous_high_blocks_network():
    root, inbox = make_inbox("success", task_id="cal3-local-high-network")
    task_path = os.path.join(inbox, "task-FakeWorker-cal3-local-high-network.md")
    write(
        task_path,
        task_text(
            root,
            task_id="cal3-local-high-network",
            modify="yes",
            run_commands="bounded",
            network_access="docs_only",
        ),
    )
    try:
        run(
            "dispatch: local autonomous high blocks network access",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-local-high-network",
                "--permission-profile",
                "cal3-local-autonomous-high",
                "--json",
            ],
            expect_exit=1,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_network_readonly_allows_network_readonly_task():
    root, inbox = make_inbox("success", task_id="cal3-network-readonly-task")
    task_path = os.path.join(inbox, "task-FakeWorker-cal3-network-readonly-task.md")
    write(
        task_path,
        task_text(
            root,
            task_id="cal3-network-readonly-task",
            modify="no",
            run_commands="read_only",
            network_access="allowed",
        ),
    )
    update_fake_capability(inbox, network_access="allowed")
    try:
        run(
            "dispatch: network readonly profile allows readonly network task",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-network-readonly-task",
                "--permission-profile",
                "cal3-network-readonly",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
        )
        status = read_status(inbox, "cal3-network-readonly-task")
        if status.get("state") != "FINISHED":
            raise AssertionError("expected FINISHED, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_network_profile_respects_cli_capability():
    root, inbox = make_inbox("success", task_id="cal3-network-capability-block")
    task_path = os.path.join(inbox, "task-FakeWorker-cal3-network-capability-block.md")
    write(
        task_path,
        task_text(
            root,
            task_id="cal3-network-capability-block",
            modify="no",
            run_commands="read_only",
            network_access="allowed",
        ),
    )
    try:
        result = run(
            "dispatch: network profile respects CLI capability ceiling",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-network-capability-block",
                "--permission-profile",
                "cal3-network-readonly",
                "--json",
            ],
            expect_exit=1,
        )
        if "network_access allowed exceeds CAL-3 profile limit none" not in result.stderr:
            raise AssertionError("expected network capability rejection, got {}".format(result.stderr))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_network_work_allows_network_edit_task():
    root, inbox = make_inbox("success", task_id="cal3-network-work-task")
    task_path = os.path.join(inbox, "task-FakeWorker-cal3-network-work-task.md")
    write(
        task_path,
        task_text(
            root,
            task_id="cal3-network-work-task",
            modify="yes",
            run_commands="bounded",
            network_access="allowed",
        ),
    )
    update_fake_capability(inbox, network_access="allowed")
    try:
        run(
            "dispatch: network work profile allows network edit task",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-network-work-task",
                "--permission-profile",
                "cal3-network-work",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "3",
                "--json",
            ],
        )
        status = read_status(inbox, "cal3-network-work-task")
        if status.get("state") != "FINISHED":
            raise AssertionError("expected FINISHED, got {}".format(status))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_approved_commit_profile_allows_worker_commit():
    root, inbox = make_inbox("commit-source", task_id="cal3-approved-commit-task")
    task_path = os.path.join(inbox, "task-FakeWorker-cal3-approved-commit-task.md")
    write(
        task_path,
        task_text(
            root,
            task_id="cal3-approved-commit-task",
            modify="yes",
            run_commands="bounded",
            network_access="allowed",
            commit_push="approved",
        ),
    )
    update_fake_capability(inbox, network_access="allowed", commit_push="approved")
    try:
        init_git_repo(root, "dispatch approved commit")
        run(
            "dispatch: approved commit profile allows worker commit",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-approved-commit-task",
                "--permission-profile",
                "cal3-approved-commit",
                "--watch-max-iterations",
                "1",
                "--poll-interval",
                "0",
                "--timeout-seconds",
                "5",
                "--json",
            ],
        )
        status = read_status(inbox, "cal3-approved-commit-task")
        if status.get("state") != "FINISHED":
            raise AssertionError("expected FINISHED, got {}".format(status))
        if status.get("commit_violations"):
            raise AssertionError("approved commit profile should not record commit violations")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_commit_approved_fails_under_non_commit_profile():
    root, inbox = make_inbox("success", task_id="cal3-commit-approved-block")
    task_path = os.path.join(inbox, "task-FakeWorker-cal3-commit-approved-block.md")
    write(
        task_path,
        task_text(
            root,
            task_id="cal3-commit-approved-block",
            modify="yes",
            run_commands="bounded",
            network_access="allowed",
            commit_push="approved",
        ),
    )
    update_fake_capability(inbox, network_access="allowed", commit_push="approved")
    try:
        result = run(
            "dispatch: commit approved fails under non-commit profile",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-commit-approved-block",
                "--permission-profile",
                "cal3-network-work",
                "--json",
            ],
            expect_exit=1,
        )
        if "commit_push approved exceeds CAL-3 profile limit no" not in result.stderr:
            raise AssertionError("expected commit_push profile rejection, got {}".format(result.stderr))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_destructive_actions_rejected_for_all_profiles():
    profiles = [
        "cal3-readonly",
        "cal3-bounded-edit",
        "cal3-local-autonomous",
        "cal3-local-autonomous-high",
        "cal3-network-readonly",
        "cal3-network-work",
        "cal3-approved-commit",
        "cal3-release-gated",
    ]
    for profile in profiles:
        root, inbox = make_inbox("success", task_id="cal3-destructive-{}".format(profile))
        task_path = os.path.join(inbox, "task-FakeWorker-cal3-destructive-{}.md".format(profile))
        write(
            task_path,
            task_text(
                root,
                task_id="cal3-destructive-{}".format(profile),
                modify="yes",
                run_commands="bounded",
                network_access="none",
                commit_push="no",
                destructive_actions="yes",
            ),
        )
        try:
            result = run(
                "dispatch: destructive actions rejected for {}".format(profile),
                [
                    sys.executable,
                    "-B",
                    DISPATCH,
                    "--inbox",
                    inbox,
                    "--task-id",
                    "cal3-destructive-{}".format(profile),
                    "--permission-profile",
                    profile,
                    "--json",
                ],
                expect_exit=1,
            )
            if "destructive_actions must remain disabled for CAL-3" not in result.stderr:
                raise AssertionError("expected destructive rejection, got {}".format(result.stderr))
        finally:
            shutil.rmtree(root, ignore_errors=True)


def test_dispatch_cli_capability_blocks_write():
    root, inbox = make_inbox("success", task_id="cal3-capability-block")
    task_path = os.path.join(inbox, "task-FakeWorker-cal3-capability-block.md")
    write(task_path, task_text(root, task_id="cal3-capability-block", modify="yes", run_commands="none"))
    recipe_path = os.path.join(inbox, "invoke-recipes.json")
    with open(recipe_path, "r", encoding="utf-8") as handle:
        recipe = json.load(handle)
    recipe["recipes"]["fake"]["capability"]["modify_source"] = False
    write(recipe_path, json.dumps(recipe, indent=2))
    try:
        run(
            "dispatch: CLI capability blocks modify_source",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-capability-block",
                "--permission-profile",
                "cal3-bounded-edit",
            ],
            expect_exit=1,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_whole_workspace_lock_overlaps():
    root, inbox = make_inbox("success", task_id="cal3-whole-lock")
    first = os.path.join(inbox, "task-FakeWorker-cal3-whole-lock.md")
    second = os.path.join(inbox, "task-FakeWorker-cal3-narrow-lock.md")
    write(first, task_text(root, task_id="cal3-whole-lock", locked="."))
    write(second, task_text(root, task_id="cal3-narrow-lock", locked="src/file.py"))
    try:
        result = run(
            "dispatch: whole-workspace lock overlaps narrow lock",
            [
                sys.executable,
                "-B",
                DISPATCH,
                "--inbox",
                inbox,
                "--task-id",
                "cal3-whole-lock",
                "--task-id",
                "cal3-narrow-lock",
                "--max-workers",
                "2",
                "--dry-run",
            ],
            expect_exit=1,
        )
        if "overlaps" not in result.stderr:
            raise AssertionError("expected overlap error, got {}".format(result.stderr))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_dispatch_rework_fuse():
    root, inbox = make_inbox("success", task_id="cal3-fuse")
    try:
        base_cmd = [
            sys.executable,
            "-B",
            DISPATCH,
            "--inbox",
            inbox,
            "--task-id",
            "cal3-fuse",
            "--watch-max-iterations",
            "5",
            "--poll-interval",
            "0",
            "--timeout-seconds",
            "3",
            "--max-attempts",
            "2",
            "--json",
        ]
        run("dispatch: fuse attempt 1", base_cmd)
        report = os.path.join(inbox, "report-FakeWorker-cal3-fuse.md")
        if os.path.exists(report):
            os.remove(report)
        run("dispatch: fuse attempt 2", base_cmd)
        if os.path.exists(report):
            os.remove(report)
        result = run(
            "dispatch: fuse attempt 3 manual fallback",
            base_cmd,
            expect_exit=2,
        )
        if "rework_fuse_tripped" not in result.stdout:
            raise AssertionError("expected rework_fuse_tripped in stdout")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_release_executor_dry_run_and_allowlist():
    root = tempfile.mkdtemp(prefix="afc-cal3-release-")
    old_cwd = os.getcwd()
    try:
        os.chdir(root)
        run("release: git init", ["git", "init", "-b", "main"], timeout=10)
        run("release: git config email", ["git", "config", "user.email", "fixture@example.com"])
        run("release: git config name", ["git", "config", "user.name", "Fixture"])
        inbox = os.path.join(root, ".agent-inbox")
        os.makedirs(inbox, exist_ok=True)
        write(os.path.join(root, "allowed.txt"), "one\n")
        run("release: initial add", ["git", "add", "allowed.txt"])
        run("release: initial commit", ["git", "commit", "-m", "test: initial"])
        write(os.path.join(root, "allowed.txt"), "two\n")
        task = task_text(
            root,
            task_id="release-dry-run",
            agent_name="ReleaseOperator",
            modify="yes",
            run_commands="bounded",
            report_name="report-ReleaseOperator-release-dry-run.md",
            locked="allowed.txt",
        ).replace("commit_push: no", "commit_push: approved")
        task += "\n## Release Operations Scope\n- Allowed operations: commit, push\n"
        task_path = os.path.join(inbox, "task-ReleaseOperator-release-dry-run.md")
        write(task_path, task)
        report = """---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: release-dry-run
agent_name: ReleaseOperator
verdict: GO
changed_files:
  - allowed.txt
evidence_refs:
  - git diff --stat
evidence_trust:
  trust_level: referenced
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
reported_at: 2026-06-19
---
# Release report
"""
        write(os.path.join(inbox, "report-ReleaseOperator-release-dry-run.md"), report)
        run(
            "release: dry run passes allowlist",
            [
                sys.executable,
                "-B",
                RELEASE,
                "--task",
                task_path,
                "--commit-message",
                "test: release fixture",
                "--json",
            ],
        )
        dot_task = task_text(
            root,
            task_id="release-dot-scope",
            agent_name="ReleaseOperator",
            modify="yes",
            run_commands="bounded",
            report_name="report-ReleaseOperator-release-dot-scope.md",
            locked=".",
        ).replace("commit_push: no", "commit_push: approved")
        dot_task += "\n## Release Operations Scope\n- Allowed operations: commit, push\n"
        dot_task_path = os.path.join(inbox, "task-ReleaseOperator-release-dot-scope.md")
        write(dot_task_path, dot_task)
        write(
            os.path.join(inbox, "report-ReleaseOperator-release-dot-scope.md"),
            report.replace("task_id: release-dry-run", "task_id: release-dot-scope"),
        )
        result = run(
            "release: dry run rejects whole-workspace allowlist",
            [
                sys.executable,
                "-B",
                RELEASE,
                "--task",
                dot_task_path,
                "--commit-message",
                "test: release fixture",
            ],
            expect_exit=1,
        )
        if "whole-workspace" not in result.stderr:
            raise AssertionError("expected whole-workspace scope error, got {}".format(result.stderr))
        write(os.path.join(root, "outside.txt"), "outside\n")
        run(
            "release: dry run rejects outside allowlist",
            [
                sys.executable,
                "-B",
                RELEASE,
                "--task",
                task_path,
                "--commit-message",
                "test: release fixture",
            ],
            expect_exit=1,
        )
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(root, ignore_errors=True)


def make_release_fixture():
    root = tempfile.mkdtemp(prefix="afc-cal3-release-")
    old_cwd = os.getcwd()
    os.chdir(root)
    run("release: git init", ["git", "init", "-b", "main"], timeout=10)
    run("release: git config email", ["git", "config", "user.email", "fixture@example.com"])
    run("release: git config name", ["git", "config", "user.name", "Fixture"])
    inbox = os.path.join(root, ".agent-inbox")
    os.makedirs(inbox, exist_ok=True)
    write(os.path.join(root, "allowed.txt"), "one\n")
    run("release: initial add", ["git", "add", "allowed.txt"])
    run("release: initial commit", ["git", "commit", "-m", "test: initial"])
    write(os.path.join(root, "allowed.txt"), "two\n")
    task = task_text(
        root,
        task_id="release-execute",
        agent_name="ReleaseOperator",
        modify="yes",
        run_commands="bounded",
        report_name="report-ReleaseOperator-release-execute.md",
        locked="allowed.txt",
    ).replace("commit_push: no", "commit_push: approved")
    task += "\n## Release Operations Scope\n- Allowed operations: commit, push\n"
    task_path = os.path.join(inbox, "task-ReleaseOperator-release-execute.md")
    write(task_path, task)
    report = """---
schema: agent-file-coordination/report
schema_version: 0.1.0
task_id: release-execute
agent_name: ReleaseOperator
verdict: GO
changed_files:
  - allowed.txt
evidence_refs:
  - git diff --stat
evidence_trust:
  trust_level: referenced
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
reported_at: 2026-06-19
---
# Release report
"""
    write(os.path.join(inbox, "report-ReleaseOperator-release-execute.md"), report)
    return root, old_cwd, task_path


def test_release_push_requires_approval():
    root, old_cwd, task_path = make_release_fixture()
    try:
        result = run(
            "release: push requires approval",
            [
                sys.executable,
                "-B",
                RELEASE,
                "--task",
                task_path,
                "--commit-message",
                "test: release fixture",
                "--coordinator-go",
                "--execute",
                "--push",
            ],
            expect_exit=1,
        )
        if "requires --push-approved" not in result.stderr:
            raise AssertionError("expected push approval error")
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(root, ignore_errors=True)


def test_release_execute_commit():
    root, old_cwd, task_path = make_release_fixture()
    try:
        result = run(
            "release: execute commit",
            [
                sys.executable,
                "-B",
                RELEASE,
                "--task",
                task_path,
                "--commit-message",
                "test: release fixture",
                "--coordinator-go",
                "--execute",
                "--json",
            ],
        )
        payload = json.loads(result.stdout)
        if payload.get("state") != "COMMITTED":
            raise AssertionError("expected COMMITTED, got {}".format(payload))
        if not payload.get("commit"):
            raise AssertionError("expected commit hash")
    finally:
        os.chdir(old_cwd)
        shutil.rmtree(root, ignore_errors=True)


def main():
    print("Running CAL-3 fixture tests...")
    test_probe_missing_inbox()
    test_probe_codex_readonly_writes_report()
    test_probe_codex_launcher()
    test_probe_codex_launcher_missing_fails_closed()
    test_dispatch_timeout_kills_process_tree()
    test_dispatch_timeout_records_source_residue()
    test_dispatch_timeout_records_commit_residue()
    test_cal3_event_metadata_validation()
    test_dispatch_heartbeat_is_liveness_not_completion()
    test_dispatch_no_progress_abort_kills_worker()
    test_dispatch_no_progress_abort_records_source_residue()
    test_dispatch_no_progress_abort_records_commit_residue()
    test_dispatch_no_progress_abort_promotes_approval_required()
    test_dispatch_no_progress_does_not_abort_completed_worker()
    test_dispatch_repeated_failure_abort()
    test_dispatch_repeated_failure_abort_from_stdout()
    test_dispatch_success()
    test_dispatch_missing_probe_blocks_automatic_dispatch()
    test_dispatch_report_path_outside_workspace()
    test_dispatch_process_exit_validates_report_before_watcher()
    test_dispatch_readonly_report_only_passes()
    test_dispatch_readonly_source_violation()
    test_dispatch_readonly_source_residue_recorded_on_failed_exit()
    test_dispatch_readonly_predirty_file_reedit_violation()
    test_dispatch_commit_violation()
    test_dispatch_invalid_report_state()
    test_dispatch_guardrail_yes_is_invalid()
    test_dispatch_report_agent_name_mismatch_is_invalid()
    test_dispatch_readonly_changed_files_is_invalid()
    test_prompt_includes_coordination_metadata()
    test_dispatch_dry_run_does_not_write_events()
    test_dispatch_dry_run_records_env_keys_only()
    test_dispatch_status_labels_worktree_as_cwd()
    test_dispatch_stdin_approval_does_not_hang()
    test_dispatch_prompt_contains_report_template()
    test_dispatch_no_report()
    test_dispatch_approval_required()
    test_dispatch_permission_profile_blocks_write()
    test_dispatch_local_autonomous_high_allows_bounded_local_work()
    test_dispatch_local_autonomous_high_blocks_network()
    test_dispatch_network_readonly_allows_network_readonly_task()
    test_dispatch_network_profile_respects_cli_capability()
    test_dispatch_network_work_allows_network_edit_task()
    test_dispatch_approved_commit_profile_allows_worker_commit()
    test_dispatch_commit_approved_fails_under_non_commit_profile()
    test_dispatch_destructive_actions_rejected_for_all_profiles()
    test_dispatch_cli_capability_blocks_write()
    test_dispatch_whole_workspace_lock_overlaps()
    test_dispatch_rework_fuse()
    test_release_executor_dry_run_and_allowlist()
    test_release_push_requires_approval()
    test_release_execute_commit()
    print("\n{} passed, {} failed".format(PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
