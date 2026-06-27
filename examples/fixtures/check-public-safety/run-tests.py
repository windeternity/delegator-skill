#!/usr/bin/env python3
"""Negative/positive tests for scripts/check-public-safety.py.

Proves the scanner actually FAILS (exit 1) when a forbidden tracked dir
(e.g. ``.codex/``) is present, and PASSES (exit 0) on a clean tree.

Fixtures are built in a system temp dir (outside the repo) at runtime, so
this test file itself contains no secrets and no forbidden dirs that could
trip the repo's own public-safety scan.

Run:
    python -B examples/fixtures/check-public-safety/run-tests.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
SCANNER = os.path.join(REPO_ROOT, "scripts", "check-public-safety.py")


def _run_scanner(target):
    proc = subprocess.run(
        [sys.executable, "-B", SCANNER, target],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def test_forbidden_dir_fails():
    """A forbidden tracked dir outside the fixtures allowlist must FAIL."""
    with tempfile.TemporaryDirectory() as d:
        codex_dir = os.path.join(d, ".codex")
        os.makedirs(codex_dir)
        with open(os.path.join(codex_dir, "state.json"), "w", encoding="utf-8") as f:
            f.write("{}\n")
        code, out = _run_scanner(d)
        assert code == 1, f"expected exit 1, got {code}\n{out}"
        assert "FORBIDDEN" in out.upper() or "forbidden" in out, \
            f"expected forbidden-dir failure message, got:\n{out}"


def test_clean_tree_passes():
    """A clean tree with an innocuous file must PASS (exit 0)."""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "README.md"), "w", encoding="utf-8") as f:
            f.write("# clean fixture\nno secrets, no forbidden dirs\n")
        code, out = _run_scanner(d)
        assert code == 0, f"expected exit 0, got {code}\n{out}"


def test_forbidden_dir_allowlisted_under_fixtures():
    """A forbidden dir under examples/fixtures/ is allowlisted and must PASS."""
    with tempfile.TemporaryDirectory() as d:
        nested = os.path.join(d, "examples", "fixtures", ".codex")
        os.makedirs(nested)
        with open(os.path.join(nested, "state.json"), "w", encoding="utf-8") as f:
            f.write("{}\n")
        code, out = _run_scanner(d)
        assert code == 0, f"expected exit 0 (allowlisted), got {code}\n{out}"


def main():
    tests = [
        ("forbidden_dir_fails", test_forbidden_dir_fails),
        ("clean_tree_passes", test_clean_tree_passes),
        ("forbidden_dir_allowlisted_under_fixtures", test_forbidden_dir_allowlisted_under_fixtures),
    ]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  [PASS] {name}")
        except AssertionError as e:
            failed += 1
            print(f"  [FAIL] {name}: {e}")
    if failed:
        print(f"\n{failed} test(s) failed.")
        sys.exit(1)
    print("\nAll check-public-safety tests passed.")


if __name__ == "__main__":
    main()
