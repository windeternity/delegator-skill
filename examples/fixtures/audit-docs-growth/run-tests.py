#!/usr/bin/env python3
"""Test runner for the surface-area growth gate in scripts/audit-docs.py.

The gate is advisory: it prints a WARN when scripts/*.py or references/*.md
exceed their budget but never fails the audit. Exercises under-threshold
(no WARN) and over-threshold (WARN, still exit 0).

Usage:
    python -B examples/fixtures/audit-docs-growth/run-tests.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

SCRIPT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "audit-docs.py")
)

SCRIPTS_LIMIT = 40
REFERENCES_LIMIT = 40


def run(target, expect_exit=0, label=""):
    cmd = [sys.executable, "-B", SCRIPT, target]
    result = subprocess.run(cmd, capture_output=True, text=True)
    ok = result.returncode == expect_exit
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label} (exit={result.returncode}, expected={expect_exit})")
    if not ok:
        print(f"    stdout: {result.stdout[:500]}")
        print(f"    stderr: {result.stderr[:500]}")
    return ok, result.stdout, result.stderr


def make_repo(scripts_n, references_n):
    """Build a minimal repo tree with N scripts/*.py and M references/*.md."""
    root = tempfile.mkdtemp(prefix="audit-docs-growth-")
    # A valid SKILL.md so the size gate stays clean and quiet.
    with open(os.path.join(root, "SKILL.md"), "wb") as handle:
        handle.write(b"x" * 1000)
    scripts_dir = os.path.join(root, "scripts")
    refs_dir = os.path.join(root, "references")
    os.makedirs(scripts_dir)
    os.makedirs(refs_dir)
    for i in range(scripts_n):
        with open(os.path.join(scripts_dir, f"s{i:03d}.py"), "w", encoding="utf-8") as handle:
            handle.write("# stub\n")
    for i in range(references_n):
        with open(os.path.join(refs_dir, f"r{i:03d}.md"), "w", encoding="utf-8") as handle:
            handle.write("stub\n")
    return root


def test_under_threshold_no_warn():
    """At/below budget -> exit 0, no SURFACE GROWTH advisory."""
    root = make_repo(SCRIPTS_LIMIT, REFERENCES_LIMIT)
    try:
        ok, stdout, _ = run(root, expect_exit=0, label="under-threshold-no-warn")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert "PASS" in stdout, "Expected audit PASS"
    assert "SURFACE GROWTH" not in stdout, "Did not expect advisory at/below budget"
    return ok


def test_scripts_over_threshold_warns():
    """scripts/*.py over budget -> WARN but still exit 0."""
    root = make_repo(SCRIPTS_LIMIT + 1, REFERENCES_LIMIT)
    try:
        ok, stdout, _ = run(root, expect_exit=0, label="scripts-over-threshold-warns")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert "SURFACE GROWTH" in stdout, f"Expected advisory, got: {stdout[:300]}"
    assert "scripts/*.py" in stdout, "Expected scripts/*.py in advisory"
    assert "PASS" in stdout, "Advisory must not fail the audit"
    return ok


def test_references_over_threshold_warns():
    """references/*.md over budget -> WARN but still exit 0."""
    root = make_repo(SCRIPTS_LIMIT, REFERENCES_LIMIT + 1)
    try:
        ok, stdout, _ = run(root, expect_exit=0, label="references-over-threshold-warns")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert "SURFACE GROWTH" in stdout, f"Expected advisory, got: {stdout[:300]}"
    assert "references/*.md" in stdout, "Expected references/*.md in advisory"
    assert "PASS" in stdout, "Advisory must not fail the audit"
    return ok


def main():
    print("Running audit-docs surface-growth gate fixture tests...")
    print()
    all_ok = True
    tests = [
        test_under_threshold_no_warn,
        test_scripts_over_threshold_warns,
        test_references_over_threshold_warns,
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
        print("All surface-growth gate fixture tests passed.")
        return 0
    print("Some surface-growth gate fixture tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
