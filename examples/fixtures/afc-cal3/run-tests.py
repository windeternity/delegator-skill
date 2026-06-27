#!/usr/bin/env python3
"""Fixture runner for CAL-3 probe, dispatcher, and release executor."""

import json
import os
import shutil
import subprocess
import sys
import tempfile


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
  commit_push: no
  destructive_actions: no
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
        report_name=report_name,
        locked=locked,
    )


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
                    "cal3-release-gated": {},
                },
            }
        },
    }
    write(os.path.join(inbox, "invoke-recipes.json"), json.dumps(recipe, indent=2))
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
    env.pop("AFC_CAL3_CODEX_EXE", None)
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
    test_dispatch_success()
    test_dispatch_report_path_outside_workspace()
    test_dispatch_process_exit_validates_report_before_watcher()
    test_dispatch_readonly_report_only_passes()
    test_dispatch_readonly_source_violation()
    test_dispatch_readonly_source_residue_recorded_on_failed_exit()
    test_dispatch_readonly_predirty_file_reedit_violation()
    test_dispatch_commit_violation()
    test_dispatch_invalid_report_state()
    test_dispatch_guardrail_yes_is_invalid()
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
