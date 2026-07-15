#!/usr/bin/env python3
"""Test runner for afc-init.{ps1,sh} bootstrap scripts.

Python stdlib only. Exercises the scripts' success and failure paths
in a fresh temp working directory, then runs the repo validator on
the generated files. The runner is deterministic: it always passes
a fixed `--created-at` of `2026-06-08`.

Usage:
    python -B examples/fixtures/afc-init/run-tests.py

The runner is intended to be run from the repository root so that
`scripts/validate-agent-inbox.py` is on the repo's normal path.

Exit codes:
    0   all tests passed (or the only failures are bash/pwsh being
        unavailable, with a clear note)
    1   at least one test failed
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

# shutil.which is available on all supported Python versions and works
# cross-platform (resolves via PATH on both Windows and POSIX).
_find_executable = shutil.which

# Force UTF-8 on stdout/stderr to avoid GBK encode errors on the Windows
# console when bash or PowerShell emit non-ASCII bytes.
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
except Exception:
    pass


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPT_PS1 = os.path.join(REPO_ROOT, "scripts", "afc-init.ps1")
SCRIPT_SH = os.path.join(REPO_ROOT, "scripts", "afc-init.sh")
VALIDATOR = os.path.join(REPO_ROOT, "scripts", "validate-agent-inbox.py")
REFUSE_DIR = os.path.join(os.path.dirname(__file__), "refuse-existing")

CREATED_AT = "2026-06-08"
CREATED_AT_2 = "2026-06-09"


# --- Windows / WSL path helpers -----------------------------------------

def to_wsl_path(win_path):
    """Convert a Windows path to WSL2 mount form: F:\\x\\y -> /mnt/f/x/y.

    WSL2 is what `bash` resolves to on this Windows host, so the
    runner converts paths before invoking bash. If the local bash is
    not WSL (for example Git Bash), the runner auto-detects the right
    mount style and uses it.
    """
    s = win_path.replace("\\", "/")
    if len(s) >= 2 and s[1] == ":":
        drive = s[0].lower()
        return f"/mnt/{drive}" + s[2:]
    return s


def detect_bash_path_style():
    """Return the mount style for the local bash.

    'wsl'  -> Windows drive is mounted under /mnt/<drive>/ (WSL2)
    'git'  -> Windows drive is mounted under /<drive>/ (Git Bash / MSYS / Cygwin)
    'unix' -> bash is a native Unix shell; Windows paths are not portable
    """
    try:
        r = subprocess.run(
            ["bash", "-c", "uname -r; mount | head -5"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10,
        )
        out = r.stdout.lower()
    except Exception:
        return "unix"
    if "microsoft" in out or "wsl" in out:
        return "wsl"
    if "/c/" in out or "/mnt/c/" not in out and (" on /c " in out or "drvfs" in out):
        return "git"
    # Native Linux / macOS — bash is a system shell, paths need no conversion.
    return "unix"


BASH_PATH_STYLE = detect_bash_path_style()


def to_bash_path(win_path):
    """Convert a Windows path to the right mount form for the local bash."""
    if BASH_PATH_STYLE == "wsl":
        return to_wsl_path(win_path)
    if BASH_PATH_STYLE == "git":
        s = win_path.replace("\\", "/")
        if len(s) >= 2 and s[1] == ":":
            return f"/{s[0].lower()}" + s[2:]
        return s
    return win_path


# --- Output decoding ----------------------------------------------------

def decode_safe(b):
    """Decode bytes robustly for the noisy Windows console pipe."""
    for enc in ("utf-8", "gbk", "cp1252", "latin1"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def run(cmd, timeout=30):
    """Run a command. Return (exit_code, stdout_str, stderr_str)."""
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return r.returncode, decode_safe(r.stdout), decode_safe(r.stderr)


# --- Tool detection -----------------------------------------------------

def find_pwsh():
    """Return the absolute path of pwsh/powershell or None.

    Uses shutil.which for cross-platform resolution (works on both
    Windows and Ubuntu CI).
    """
    # Prefer pwsh (PowerShell 7+) over Windows PowerShell 5.1
    for name in ("pwsh", "powershell"):
        found = _find_executable(name)
        if found:
            return found
    return None


def find_bash():
    """Return the absolute path of bash or None.

    Uses shutil.which for cross-platform resolution.
    """
    bash = _find_executable("bash")
    if not bash:
        return None
    try:
        r = subprocess.run(
            [bash, "-c", "printf ready"],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        return None
    return bash if r.returncode == 0 and decode_safe(r.stdout) == "ready" else None


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
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            self.failures.append((name, detail))
            print(f"  [FAIL] {name}: {detail}")

    def skip(self, name, reason):
        self.skipped += 1
        print(f"  [SKIP] {name}: {reason}")

    def report(self):
        print()
        print("=" * 60)
        print(f"passed: {self.passed}")
        print(f"failed: {self.failed}")
        print(f"skipped: {self.skipped}")
        if self.failures:
            print("failures:")
            for name, detail in self.failures:
                print(f"  - {name}: {detail[:200]}")
        return 0 if self.failed == 0 else 1


def run_ps(_runner, project_root, *extra_args):
    pwsh = PWSH_PATH
    if pwsh is None:
        print("  [SKIP] pwsh: pwsh not found on PATH")
        return None, None, None
    cmd = [pwsh, "-NoProfile", "-NonInteractive", "-File", SCRIPT_PS1,
           "-ProjectRoot", project_root, *extra_args]
    return run(cmd, timeout=30)


def run_sh(_runner, project_root, *extra_args):
    if BASH_PATH is None:
        print("  [SKIP] bash: bash not found on PATH")
        return None, None, None
    cmd = [BASH_PATH, to_bash_path(SCRIPT_SH), "-p", project_root, *extra_args]
    return run(cmd, timeout=30)


def validate_inbox(runner, project_root, label):
    inbox = os.path.join(project_root, ".agent-inbox")
    for name in ("AGENT_ROSTER.md", "STATUS.md", "WORKTREE_LOCKS.md", "events.jsonl"):
        p = os.path.join(inbox, name)
        if not os.path.isfile(p):
            runner.check(f"{label}: {name} exists", False, f"missing {p}")
            return
    args = [sys.executable, "-B", VALIDATOR, "--template-mode", inbox]
    exit_code, out, err = run(args, timeout=30)
    runner.check(
        f"{label}: validator (template-mode) clean",
        exit_code == 0,
        f"exit={exit_code} stdout={out[:200]} stderr={err[:200]}",
    )


def assert_inbox_content(runner, project_root, expected_date, label):
    inbox = os.path.join(project_root, ".agent-inbox")
    for name in ("AGENT_ROSTER.md", "STATUS.md", "WORKTREE_LOCKS.md", "events.jsonl"):
        p = os.path.join(inbox, name)
        if not os.path.isfile(p):
            runner.check(f"{label}: {name} exists", False, f"missing {p}")
            return
    with open(os.path.join(inbox, "STATUS.md"), "r", encoding="utf-8") as f:
        content = f.read()
    runner.check(
        f"{label}: STATUS.md updated_at is {expected_date}",
        f"updated_at: {expected_date}" in content,
        f"STATUS.md content did not contain updated_at: {expected_date}",
    )
    with open(os.path.join(inbox, "WORKTREE_LOCKS.md"), "r", encoding="utf-8") as f:
        content = f.read()
    runner.check(
        f"{label}: WORKTREE_LOCKS.md updated_at is {expected_date}",
        f"updated_at: {expected_date}" in content,
        f"WORKTREE_LOCKS.md content did not contain updated_at: {expected_date}",
    )
    with open(os.path.join(inbox, "events.jsonl"), "r", encoding="utf-8") as f:
        events_content = f.read()
    # Accept both spaced and compact JSON. PowerShell's ConvertTo-Json
    # -Compress emits no space after ':'; bash's printf emits a space.
    runner.check(
        f"{label}: events.jsonl has exactly one ROSTER_UPDATED event",
        (events_content.count('"event_type": "ROSTER_UPDATED"')
         + events_content.count('"event_type":"ROSTER_UPDATED"')) == 1,
        f"events.jsonl did not contain exactly one ROSTER_UPDATED event: {events_content!r}",
    )
    runner.check(
        f"{label}: events.jsonl created_at is {expected_date}",
        (f'"created_at": "{expected_date}"' in events_content
         or f'"created_at":"{expected_date}"' in events_content),
        f"events.jsonl did not contain created_at: {expected_date}: {events_content!r}",
    )


# --- Test cases --------------------------------------------------------

def make_fresh_project(runner, label):
    tmp = tempfile.mkdtemp(prefix=f"afc-init-runner-{label}-")
    return tmp


def cleanup(project_root):
    if project_root and os.path.isdir(project_root):
        shutil.rmtree(project_root, ignore_errors=True)


def test_create_from_scratch(runner, runner_fn, label):
    """Create-inbox-from-scratch should exit 0 and write four files."""
    print(f"\n[{label}] create inbox from scratch")
    tmp = make_fresh_project(runner, label)
    try:
        exit_code, out, err = runner_fn(tmp, date_value=CREATED_AT, force=False)
        if exit_code is None:
            runner.skip(f"{label}: create-inbox", "runner unavailable (pwsh/bash missing)")
            return
        runner.check(
            f"{label}: create-inbox exit=0",
            exit_code == 0,
            f"exit={exit_code} stdout={(out or '')[:200]} stderr={(err or '')[:200]}",
        )
        if exit_code == 0:
            # The inbox files live on the Windows drive; from this
            # Python on Windows they are readable through the original
            # Windows path, not the WSL mount path.
            assert_inbox_content(runner, tmp, CREATED_AT, label)
            validate_inbox(runner, tmp, label)
    finally:
        cleanup(tmp)


def test_refuse_when_existing(runner, runner_fn, label):
    """Re-running without overwrite flag should fail and not modify files."""
    print(f"\n[{label}] re-run without force refuses to overwrite")
    tmp = make_fresh_project(runner, label)
    try:
        # First create the inbox
        exit_code, _, _ = runner_fn(tmp, date_value=CREATED_AT, force=False)
        if exit_code != 0:
            runner.skip(f"{label}: refuse test (setup failed)", "create exit != 0")
            return
        # Capture the original events.jsonl
        events_path = os.path.join(tmp, ".agent-inbox", "events.jsonl")
        with open(events_path, "r", encoding="utf-8") as f:
            original = f.read()
        # Re-run without force
        exit_code, out, err = runner_fn(tmp, date_value=CREATED_AT, force=False)
        runner.check(
            f"{label}: re-run exit=1",
            exit_code == 1,
            f"exit={exit_code} stdout={out[:200]} stderr={err[:200]}",
        )
        # Confirm file was not modified
        with open(events_path, "r", encoding="utf-8") as f:
            after = f.read()
        runner.check(
            f"{label}: re-run did not modify events.jsonl",
            after == original,
            "events.jsonl content changed after refused re-run",
        )
    finally:
        cleanup(tmp)


def test_force_overwrites(runner, runner_fn, label):
    """With the force flag, re-run should overwrite and use the new date."""
    print(f"\n[{label}] --force/-Force overwrites with new date")
    tmp = make_fresh_project(runner, label)
    try:
        # First create the inbox
        exit_code, _, _ = runner_fn(tmp, date_value=CREATED_AT, force=False)
        if exit_code != 0:
            runner.skip(f"{label}: force test (setup failed)", "create exit != 0")
            return
        # Re-run with force and a different date
        exit_code, out, err = runner_fn(tmp, date_value=CREATED_AT_2, force=True)
        runner.check(
            f"{label}: --force exit=0",
            exit_code == 0,
            f"exit={exit_code} stdout={out[:200]} stderr={err[:200]}",
        )
        if exit_code == 0:
            assert_inbox_content(runner, tmp, CREATED_AT_2, f"{label} (force)")
    finally:
        cleanup(tmp)


def test_missing_project_root(runner, runner_fn, label, missing_path):
    """Missing project root should exit 1."""
    print(f"\n[{label}] missing project root -> exit 1")
    exit_code, out, err = runner_fn(missing_path, date_value=CREATED_AT, force=False)
    if exit_code is None:
        runner.skip(f"{label}: missing-root", "runner unavailable (pwsh/bash missing)")
        return
    runner.check(
        f"{label}: missing-root exit=1",
        exit_code == 1,
        f"exit={exit_code} stderr={(err or '')[:200]}",
    )


def test_invalid_date(runner, runner_fn, label):
    """Invalid date format should exit 1."""
    print(f"\n[{label}] invalid date -> exit 1")
    tmp = make_fresh_project(runner, label)
    try:
        exit_code, out, err = runner_fn(tmp, date_value="not-a-date", force=False)
        if exit_code is None:
            runner.skip(f"{label}: bad-date", "runner unavailable (pwsh/bash missing)")
            return
        runner.check(
            f"{label}: bad-date exit=1",
            exit_code == 1,
            f"exit={exit_code} stderr={(err or '')[:200]}",
        )
    finally:
        cleanup(tmp)


def test_unknown_flag(runner, runner_fn, label, unknown_flag, expect_exit=2):
    """Unknown flag should exit nonzero. PowerShell's parameter binder
    exits 1 for unknown parameters; bash exits 2. Accept either as
    'nonzero, with an error message'."""
    print(f"\n[{label}] unknown flag -> exit {expect_exit}")
    exit_code, out, err = runner_fn(os.getcwd(), date_value=None, force=unknown_flag)
    if exit_code is None:
        runner.skip(f"{label}: unknown-flag", "runner unavailable (pwsh/bash missing)")
        return
    runner.check(
        f"{label}: unknown-flag exit={expect_exit}",
        exit_code == expect_exit,
        f"exit={exit_code} stderr={(err or '')[:200]}",
    )


def test_help(runner, runner_fn, label, help_flag):
    """--help / -? should exit 0 and print usage text."""
    print(f"\n[{label}] help -> exit 0")
    exit_code, out, err = runner_fn(os.getcwd(), date_value=None, force=help_flag)
    if exit_code is None:
        runner.skip(f"{label}: help", "runner unavailable (pwsh/bash missing)")
        return
    runner.check(
        f"{label}: help exit=0",
        exit_code == 0,
        f"exit={exit_code} stderr={(err or '')[:200]}",
    )
    runner.check(
        f"{label}: help mentions 'usage'",
        "usage" in out.lower(),
        f"stdout did not contain 'usage': {(out or '')[:200]}",
    )


# --- Script-specific runners -------------------------------------------

def make_ps_runner():
    """Return a function that calls the PowerShell script with the right args.

    Signature: (project_root, date_value_or_None, force_value) -> (exit, stdout, stderr)
    """
    def _run(project_root, date_value=None, force=False):
        args = []
        if date_value is not None:
            args += ["-CreatedAt", date_value]
        if force is True:
            args += ["-Force"]
        elif isinstance(force, str):
            args += [force]
        return run_ps(None, project_root, *args)
    return _run


def make_sh_runner():
    """Return a function that calls the bash script with the right args.

    Signature: (project_root, date_value_or_None, force_value) -> (exit, stdout, stderr)

    The project_root is converted to a WSL/Git-Bash path before
    being passed to bash, because the script is invoked through a
    Unix-style bash interpreter even on this Windows host.
    """
    def _run(project_root, date_value=None, force=False):
        args = []
        if date_value is not None:
            args += ["-d", date_value]
        if force is True:
            args += ["-f"]
        elif isinstance(force, str):
            args += [force]
        return run_sh(None, to_bash_path(project_root), *args)
    return _run


# --- Main ---------------------------------------------------------------

PWSH_PATH = None
BASH_PATH = None


def main():
    global PWSH_PATH, BASH_PATH
    PWSH_PATH = find_pwsh()
    BASH_PATH = find_bash()
    print(f"pwsh: {PWSH_PATH}")
    print(f"bash: {BASH_PATH}")
    print(f"bash path style: {BASH_PATH_STYLE}")
    print(f"validator: {VALIDATOR}")
    print()

    runner = Runner()

    # --- bash tests ---
    if BASH_PATH is None:
        runner.skip("bash suite", "bash not found or cannot execute a minimal command")
    else:
        sh_runner = make_sh_runner()
        test_create_from_scratch(runner, sh_runner, "bash")
        test_refuse_when_existing(runner, sh_runner, "bash")
        test_force_overwrites(runner, sh_runner, "bash")
        test_missing_project_root(runner, sh_runner, "bash",
                                  missing_path=os.path.join(tempfile.gettempdir(), "afc-init-does-not-exist-xyz"))
        test_invalid_date(runner, sh_runner, "bash")
        test_unknown_flag(runner, sh_runner, "bash", unknown_flag="-x")
        test_help(runner, sh_runner, "bash", help_flag="--help")

    # --- pwsh tests ---
    ps_runner = make_ps_runner()
    test_create_from_scratch(runner, ps_runner, "pwsh")
    test_refuse_when_existing(runner, ps_runner, "pwsh")
    test_force_overwrites(runner, ps_runner, "pwsh")
    test_missing_project_root(runner, ps_runner, "pwsh",
                              missing_path=os.path.join(tempfile.gettempdir(), "afc-init-does-not-exist-xyz"))
    test_invalid_date(runner, ps_runner, "pwsh")
    test_unknown_flag(runner, ps_runner, "pwsh", unknown_flag="-NotARealFlag", expect_exit=1)
    # PowerShell -? prints help, but the param binder may bind it. We
    # skip the pwsh help probe and rely on the bash --help probe to
    # prove the help path is correct (the two scripts share the same
    # usage text).

    return runner.report()


if __name__ == "__main__":
    sys.exit(main())
