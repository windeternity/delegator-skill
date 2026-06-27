#!/usr/bin/env python3
"""Fixture runner for summarize-codex-usage.py.

Exercises success and failure cases using the JSONL fixture data
in this directory. Returns exit 0 when all checks pass.

Usage:
    python -B examples/fixtures/codex-usage/run-tests.py
"""

import json
import os
import subprocess
import sys

SCRIPT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "summarize-codex-usage.py")
)
BASE = os.path.dirname(os.path.abspath(__file__))

PASS = 0
FAIL = 0


def run(label, cmd, expect_exit=0):
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
    return r


def test_single_label():
    """Single LABEL=PATH produces correct per-label and aggregate totals."""
    fixture = os.path.join(BASE, "valid-single-label.jsonl")
    r = run(
        "single-label: text output",
        [sys.executable, "-B", SCRIPT, f"alpha={fixture}"],
        expect_exit=0,
    )
    if r.returncode != 0:
        return
    # alpha should have input 300 (100+200), cached 100 (40+60), output 130 (50+80)
    if "=== alpha ===" not in r.stdout:
        FAIL += 1
        print("  [FAIL] single-label: missing '=== alpha ===' header")
    if "=== aggregate ===" not in r.stdout:
        FAIL += 1
        print("  [FAIL] single-label: missing '=== aggregate ===' header")


def test_single_label_json():
    """--json output is valid JSON with expected structure."""
    fixture = os.path.join(BASE, "valid-single-label.jsonl")
    r = run(
        "single-label-json",
        [sys.executable, "-B", SCRIPT, "--json", f"alpha={fixture}"],
        expect_exit=0,
    )
    if r.returncode != 0:
        return
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        FAIL += 1
        print(f"  [FAIL] single-label-json: not valid JSON: {r.stdout[:300]}")
        return

    if "per_label" not in data or "aggregate" not in data:
        FAIL += 1
        print("  [FAIL] single-label-json: missing 'per_label' or 'aggregate'")
        return

    alpha = data["per_label"].get("alpha")
    if not alpha:
        FAIL += 1
        print("  [FAIL] single-label-json: missing 'alpha' in per_label")
        return

    # 100 + 200 = 300 input; 40 + 60 = 100 cached; 50 + 80 = 130 output
    if alpha["input_tokens"] != 300:
        FAIL += 1
        print(f"  [FAIL] single-label-json: input_tokens={alpha['input_tokens']}, expected 300")
    if alpha["cached_input_tokens"] != 100:
        FAIL += 1
        print(f"  [FAIL] single-label-json: cached_input_tokens={alpha['cached_input_tokens']}, expected 100")
    if alpha["output_tokens"] != 130:
        FAIL += 1
        print(f"  [FAIL] single-label-json: output_tokens={alpha['output_tokens']}, expected 130")
    if alpha["total_tokens"] != 430:
        FAIL += 1
        print(f"  [FAIL] single-label-json: total_tokens={alpha['total_tokens']}, expected 430")
    if alpha["usage_events"] != 2:
        FAIL += 1
        print(f"  [FAIL] single-label-json: usage_events={alpha['usage_events']}, expected 2")


def test_two_labels_aggregate():
    """Two labels produce per-label and correct aggregate."""
    f1 = os.path.join(BASE, "valid-single-label.jsonl")
    f2 = os.path.join(BASE, "valid-second-label.jsonl")
    r = run(
        "two-labels",
        [sys.executable, "-B", SCRIPT, "--json", f"alpha={f1}", f"beta={f2}"],
        expect_exit=0,
    )
    if r.returncode != 0:
        return
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        FAIL += 1
        print(f"  [FAIL] two-labels: not valid JSON")
        return

    agg = data["aggregate"]
    # alpha: 300 input, 130 output; beta: 11 input, 22 output
    if agg["input_tokens"] != 311:
        FAIL += 1
        print(f"  [FAIL] two-labels: aggregate input={agg['input_tokens']}, expected 311")
    if agg["output_tokens"] != 152:
        FAIL += 1
        print(f"  [FAIL] two-labels: aggregate output={agg['output_tokens']}, expected 152")


def test_desktop_token_count():
    """Desktop token_count events use final cumulative snapshot."""
    fixture = os.path.join(BASE, "valid-desktop-token-count.jsonl")
    r = run(
        "desktop-token-count",
        [sys.executable, "-B", SCRIPT, "--json", f"desktop={fixture}"],
        expect_exit=0,
    )
    if r.returncode != 0:
        return
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        FAIL += 1
        print("  [FAIL] desktop-token-count: not valid JSON")
        return

    d = data["per_label"].get("desktop")
    if not d:
        FAIL += 1
        print("  [FAIL] desktop-token-count: missing 'desktop' in per_label")
        return

    # Final cumulative snapshot: input=286238, cached=231680, output=3029, reasoning=532
    if d["input_tokens"] != 286238:
        FAIL += 1
        print(f"  [FAIL] desktop-token-count: input={d['input_tokens']}, expected 286238")
    if d["cached_input_tokens"] != 231680:
        FAIL += 1
        print(f"  [FAIL] desktop-token-count: cached={d['cached_input_tokens']}, expected 231680")
    if d["output_tokens"] != 3029:
        FAIL += 1
        print(f"  [FAIL] desktop-token-count: output={d['output_tokens']}, expected 3029")


def test_nested_form():
    """Nested turn.completed events are recognized."""
    fixture = os.path.join(BASE, "valid-nested-form.jsonl")
    r = run(
        "nested-form",
        [sys.executable, "-B", SCRIPT, "--json", f"nested={fixture}"],
        expect_exit=0,
    )
    if r.returncode != 0:
        return
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        FAIL += 1
        print("  [FAIL] nested-form: not valid JSON")
        return

    n = data["per_label"].get("nested")
    if not n:
        FAIL += 1
        print("  [FAIL] nested-form: missing 'nested' in per_label")
        return

    # 7+3=10 input, 14+4=18 output, 0+1=1 reasoning
    if n["input_tokens"] != 10:
        FAIL += 1
        print(f"  [FAIL] nested-form: input={n['input_tokens']}, expected 10")
    if n["output_tokens"] != 18:
        FAIL += 1
        print(f"  [FAIL] nested-form: output={n['output_tokens']}, expected 18")
    if n["reasoning_output_tokens"] != 1:
        FAIL += 1
        print(f"  [FAIL] nested-form: reasoning={n['reasoning_output_tokens']}, expected 1")


def test_canonical_wins():
    """cached_input_tokens is preferred over cache_read_input_tokens."""
    fixture = os.path.join(BASE, "valid-canonical-wins.jsonl")
    r = run(
        "canonical-wins",
        [sys.executable, "-B", SCRIPT, "--json", f"canon={fixture}"],
        expect_exit=0,
    )
    if r.returncode != 0:
        return
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        FAIL += 1
        print("  [FAIL] canonical-wins: not valid JSON")
        return

    c = data["per_label"].get("canon")
    if not c:
        FAIL += 1
        print("  [FAIL] canonical-wins: missing 'canon' in per_label")
        return

    # turn-1 has both cached_input_tokens=400 and cache_read_input_tokens=999
    # canonical wins: 400. turn-2 only has cache_read_input_tokens=123, used as fallback.
    # Total cached: 400 + 123 = 523
    if c["cached_input_tokens"] != 523:
        FAIL += 1
        print(f"  [FAIL] canonical-wins: cached={c['cached_input_tokens']}, expected 523")


def test_real_codex():
    """Real Codex log with large token counts parses correctly."""
    fixture = os.path.join(BASE, "valid-real-codex.jsonl")
    r = run(
        "real-codex",
        [sys.executable, "-B", SCRIPT, "--json", f"real={fixture}"],
        expect_exit=0,
    )
    if r.returncode != 0:
        return
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        FAIL += 1
        print("  [FAIL] real-codex: not valid JSON")
        return

    rc = data["per_label"].get("real")
    if not rc:
        FAIL += 1
        print("  [FAIL] real-codex: missing 'real' in per_label")
        return

    # 131216+174640=305856 input; 65920+93952=159872 cached; 1430+2010=3440 output
    if rc["input_tokens"] != 305856:
        FAIL += 1
        print(f"  [FAIL] real-codex: input={rc['input_tokens']}, expected 305856")
    if rc["output_tokens"] != 3440:
        FAIL += 1
        print(f"  [FAIL] real-codex: output={rc['output_tokens']}, expected 3440")


def test_malformed_json():
    """Malformed JSON in log file causes exit 1."""
    fixture = os.path.join(BASE, "invalid-malformed.jsonl")
    run(
        "malformed: exit 1",
        [sys.executable, "-B", SCRIPT, f"bad={fixture}"],
        expect_exit=1,
    )


def test_no_usage_events():
    """Log file with no usage events causes exit 1."""
    fixture = os.path.join(BASE, "invalid-no-usage.jsonl")
    run(
        "no-usage: exit 1",
        [sys.executable, "-B", SCRIPT, f"empty={fixture}"],
        expect_exit=1,
    )


def test_require_label_pass():
    """--require-label passes when label is present."""
    fixture = os.path.join(BASE, "valid-single-label.jsonl")
    run(
        "require-label: present",
        [sys.executable, "-B", SCRIPT, "--require-label", "alpha", f"alpha={fixture}"],
        expect_exit=0,
    )


def test_require_label_fail():
    """--require-label fails when label is absent."""
    fixture = os.path.join(BASE, "valid-single-label.jsonl")
    run(
        "require-label: missing",
        [sys.executable, "-B", SCRIPT, "--require-label", "beta", f"alpha={fixture}"],
        expect_exit=1,
    )


def test_malformed_arg():
    """Argument without '=' causes exit 2."""
    run(
        "malformed-arg: exit 2",
        [sys.executable, "-B", SCRIPT, "no-equals-sign"],
        expect_exit=2,
    )


def main():
    print("Running summarize-codex-usage.py fixture tests...")
    print()
    test_single_label()
    test_single_label_json()
    test_two_labels_aggregate()
    test_desktop_token_count()
    test_nested_form()
    test_canonical_wins()
    test_real_codex()
    test_malformed_json()
    test_no_usage_events()
    test_require_label_pass()
    test_require_label_fail()
    test_malformed_arg()
    print()
    print(f"Results: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
