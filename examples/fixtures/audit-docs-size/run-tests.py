#!/usr/bin/env python3
"""Test runner for SKILL.md size gate fixtures.

Exercises the two-tier installed-weight budget enforced by
scripts/audit-docs.py: clean (at/below target), advisory tolerance band
(target < size <= hard ceiling, passes with WARN), and fail (over the hard
ceiling).

Usage:
    python -B examples/fixtures/audit-docs-size/run-tests.py
"""

import os
import subprocess
import sys
import tempfile
import shutil

SCRIPT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "audit-docs.py")
)

TARGET = 8_000
HARD = 9_000


def run(target, expect_exit=0, label=""):
    """Run audit-docs.py against target. Returns (ok, stdout, stderr)."""
    cmd = [sys.executable, "-B", SCRIPT, target]
    result = subprocess.run(cmd, capture_output=True, text=True)
    ok = result.returncode == expect_exit
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label} (exit={result.returncode}, expected={expect_exit})")
    if not ok:
        print(f"    stdout: {result.stdout[:500]}")
        print(f"    stderr: {result.stderr[:500]}")
    return ok, result.stdout, result.stderr


def make_fixture(size):
    root = tempfile.mkdtemp(prefix="audit-docs-size-")
    with open(os.path.join(root, "SKILL.md"), "wb") as handle:
        handle.write(b"x" * size)
    return root


def test_pass_at_target():
    """SKILL.md exactly at the 8,000 byte target -> exit 0, no advisory."""
    root = make_fixture(TARGET)
    try:
        ok, stdout, _ = run(root, expect_exit=0, label="pass-at-target")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert "PASS" in stdout, "Expected PASS in output"
    assert "WARN" not in stdout, "Did not expect advisory at/below target"
    return ok


def test_advisory_in_band():
    """SKILL.md over target but at/below the hard ceiling -> exit 0 with WARN."""
    size = TARGET + 1
    root = make_fixture(size)
    try:
        ok, stdout, _ = run(root, expect_exit=0, label="advisory-in-band")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert "WARN" in stdout, f"Expected advisory WARN in output, got: {stdout[:300]}"
    assert "SKILL SIZE" in stdout, "Expected 'SKILL SIZE' in advisory"
    assert "PASS" in stdout, "Expected PASS (advisory does not fail the gate)"
    return ok


def test_pass_at_hard_ceiling():
    """SKILL.md exactly at the 9,000 byte hard ceiling -> exit 0 with WARN."""
    root = make_fixture(HARD)
    try:
        ok, stdout, _ = run(root, expect_exit=0, label="pass-at-hard-ceiling")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert "WARN" in stdout, "Expected advisory WARN at the hard ceiling"
    assert "PASS" in stdout, "Expected PASS at the hard ceiling"
    return ok


def test_fail_over_hard_ceiling():
    """SKILL.md over the 9,000 byte hard ceiling -> exit 1 with clear message."""
    size = HARD + 1
    root = make_fixture(size)
    try:
        ok, stdout, _ = run(root, expect_exit=1, label="fail-over-hard-ceiling")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert "SKILL SIZE" in stdout, f"Expected 'SKILL SIZE' in output, got: {stdout[:300]}"
    assert str(size) in stdout, f"Expected actual size {size} in output"
    assert str(HARD) in stdout, f"Expected hard ceiling {HARD} in output"
    return ok


def main():
    print("Running audit-docs size gate fixture tests...")
    print()
    all_ok = True

    tests = [
        test_pass_at_target,
        test_advisory_in_band,
        test_pass_at_hard_ceiling,
        test_fail_over_hard_ceiling,
    ]

    for test_fn in tests:
        try:
            ok = test_fn()
        except Exception as exc:
            print(f"  [FAIL] {test_fn.__name__}: {exc}")
            ok = False
        if not ok:
            all_ok = False
        print()

    if all_ok:
        print("All size gate fixture tests passed.")
        return 0
    else:
        print("Some size gate fixture tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
