#!/usr/bin/env python3
"""Regression tests for the validation_command trust-boundary hardening.

The coordinator re-runs `validation_command` with shell=True. That command is
trusted because it is coordinator-authored, but if the "workers cannot write
task files" convention is ever violated the string becomes attacker-controlled.
These tests pin the defense-in-depth layer: destructive patterns and shell
chaining are rejected before execution, while legitimate single-line code gates
still run.
"""

import importlib.util
import os
import sys
import tempfile


REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
SCRIPTS = os.path.join(REPO_ROOT, "scripts")

PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print("  [PASS] {}".format(label))
    else:
        FAIL += 1
        print("  [FAIL] {}: {}".format(label, detail))


def _load_intake():
    sys.path.insert(0, SCRIPTS)
    spec = importlib.util.spec_from_file_location(
        "afc_intake", os.path.join(SCRIPTS, "afc-intake.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legitimate_commands_run():
    intake = _load_intake()
    for command in (
        "exit 0",
        "python -m pytest --version",
        "git diff --check",
        "python -B scripts/afc-route.py --estimated-direct-minutes 5",
    ):
        rc, tail = intake.run_validation_command(command, REPO_ROOT)
        check(
            "legitimate gate runs: {!r}".format(command),
            rc != 127 or "rejected" not in tail,
            "rc={} tail={}".format(rc, tail),
        )


def test_destructive_patterns_rejected():
    # Structural patterns only: these shapes never appear in a legitimate path
    # or argument, so substring matching is exact. Bare command words
    # (shutdown/reboot/mkfs) are intentionally NOT blocked -- see
    # test_command_words_always_allowed.
    intake = _load_intake()
    for command in (
        "rm -rf /tmp/anything",
        "rm -fr /tmp/anything",
        "dd if=/dev/zero of=/tmp/x",
        "echo x >/dev/sda1",
        ":(){ :|:& };:",
    ):
        rc, tail = intake.run_validation_command(command, REPO_ROOT)
        check(
            "destructive pattern rejected: {!r}".format(command),
            rc == 127 and "rejected" in tail,
            "rc={} tail={}".format(rc, tail),
        )


def test_command_words_always_allowed():
    # Bare command words (shutdown/reboot/mkfs) collide with legitimate test
    # names / selectors and cannot be distinguished from command-position without
    # a shell parser. They are allowed in all positions; the structural blocklist
    # above covers the genuinely destructive shapes.
    intake = _load_intake()
    for command in (
        "python -m pytest tests/test_shutdown.py",
        "python -m pytest tests/test_reboot_behavior.py",
        "pytest tests/test_mkfs_helper.py",
        "pytest -k shutdown",
        "pytest -k reboot",
        "pytest -k mkfs",
    ):
        rc, tail = intake.run_validation_command(command, REPO_ROOT)
        check(
            "command word always allowed: {!r}".format(command),
            "rejected" not in tail,
            "rc={} tail={}".format(rc, tail),
        )


def test_compound_gates_allowed():
    intake = _load_intake()
    # Compound gates are legitimate (lint + test, pipe to tail). They must NOT
    # be rejected for chaining alone; the blocklist catches destructive content.
    for command in (
        "ruff check . && python -m pytest",
        "python -m pytest | tail -5",
        "exit 0 || exit 1",
    ):
        rc, tail = intake.run_validation_command(command, REPO_ROOT)
        check(
            "compound gate allowed: {!r}".format(command),
            "rejected" not in tail,
            "rc={} tail={}".format(rc, tail),
        )
    # A chain that contains a destructive pattern is still caught by the
    # blocklist, regardless of the chaining operator.
    rc, tail = intake.run_validation_command("exit 0 && rm -rf /tmp/x", REPO_ROOT)
    check(
        "destructive compound gate still blocked",
        rc == 127 and "rejected" in tail,
        "rc={} tail={}".format(rc, tail),
    )


def test_output_redirect_scoped():
    intake = _load_intake()
    # Redirect to a workspace-relative file is legitimate for a code gate. Run
    # these in an isolated temp cwd so the artifact lands there, NOT in the repo
    # root (Task 5: previously this leaked log.txt into the project on every run).
    with tempfile.TemporaryDirectory(prefix="afc-vc-") as scratch:
        rc, tail = intake.run_validation_command("echo ok > log.txt", scratch)
        check(
            "workspace-relative redirect allowed: echo ok > log.txt",
            "rejected" not in tail,
            "rc={} tail={}".format(rc, tail),
        )
        check(
            "redirect artifact lands in the isolated cwd",
            os.path.isfile(os.path.join(scratch, "log.txt")),
            "expected log.txt under {}".format(scratch),
        )
        rc, tail = intake.run_validation_command("echo ok >> out.log", scratch)
        check(
            "workspace-relative append allowed: echo ok >> out.log",
            "rejected" not in tail,
            "rc={} tail={}".format(rc, tail),
        )
        check(
            "append artifact lands in the isolated cwd",
            os.path.isfile(os.path.join(scratch, "out.log")),
            "expected out.log under {}".format(scratch),
        )
    # Redirects that escape the workspace (absolute path, or `..`) are blocked.
    # These never execute, so cwd does not matter; use the repo root for stability.
    # Includes PR review #3 disguised escapes: ./../, logs/../../, a/b/../../../.
    for command in (
        "echo x > /tmp/escape.txt",
        "pytest > ../escape.txt",
        "pytest > ./../escape.txt",
        "pytest > logs/../../escape.txt",
        "pytest > a/b/../../../escape.txt",
    ):
        rc, tail = intake.run_validation_command(command, REPO_ROOT)
        check(
            "escape redirect rejected: {!r}".format(command),
            rc == 127 and "rejected" in tail,
            "rc={} tail={}".format(rc, tail),
        )
    # PR review #4: shell-expanded redirect targets (~, $VAR) land outside the
    # workspace after the shell expands them, but the raw token stays under cwd.
    # Reject them outright since their landing site is unknowable from Python.
    for command in (
        "pytest > ~/out.log",
        "pytest > $HOME/out.log",
        "pytest > ~user/out.log",
    ):
        rc, tail = intake.run_validation_command(command, REPO_ROOT)
        check(
            "shell-expanded redirect rejected: {!r}".format(command),
            rc == 127 and "rejected" in tail,
            "rc={} tail={}".format(rc, tail),
        )


def test_empty_command_passes_through():
    intake = _load_intake()
    rc, tail = intake.run_validation_command("", REPO_ROOT)
    # Empty command is not dangerous; it is filtered upstream by should_reverify
    # / the call site, so the gate simply does not reject it here.
    check(
        "empty command not flagged as dangerous",
        "rejected" not in tail,
        "rc={} tail={}".format(rc, tail),
    )


def main():
    print("Running validation_command trust-boundary regression tests...")
    test_legitimate_commands_run()
    test_destructive_patterns_rejected()
    test_command_words_always_allowed()
    test_compound_gates_allowed()
    test_output_redirect_scoped()
    test_empty_command_passes_through()
    print("\nResults: {} passed, {} failed".format(PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
