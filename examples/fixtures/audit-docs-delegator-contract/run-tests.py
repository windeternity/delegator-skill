#!/usr/bin/env python3
"""Fixture tests for Delegator's active-turn and first-use doc contract."""

import os
import shutil
import subprocess
import sys
import tempfile


AUDIT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "audit-docs.py")
)

GOOD = {
    "SKILL.md": "\n".join(
        (
            "# Skill",
            "While Delegator is active, never use helpers for exploration, review, implementation, or fallback.",
            "## Mandatory First Command",
            "afc-first-run-config.py --check-only",
            "afc-blast-radius.py",
            "afc-route.py",
            "",
        )
    ),
    "agents/openai.yaml": (
        "description: While Delegator is active, it never uses built-in subagents "
        "for exploration, review, implementation, or fallback.\n"
    ),
    "references/coordination-routing-policy.md": (
        "# Routing\nUse install-local `LOCAL_ROSTER.md` by default and an "
        "explicit project override only when requested.\n"
    ),
    "references/session-bootstrap-gate.md": (
        "# Bootstrap\nRun the check once per coordinator session. Persist the "
        "install-local `LOCAL_ROSTER.md` user profile; use an explicit project "
        "override only when requested.\n"
    ),
    "docs/FIRST_RUN.md": (
        "# First Run\nThe install-local `LOCAL_ROSTER.md` is shared. Use an "
        "explicit project override only when requested.\n"
    ),
    "scripts/afc-first-run-config.py": (
        'def cmd_check_only():\n'
        '    print("next_action: ASK_CAL")\n'
        '    return 1\n'
    ),
}


def write_surface(root, replacements=None):
    values = dict(GOOD)
    values.update(replacements or {})
    for rel, content in values.items():
        path = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)


def run_case(replacements=None, omitted=None):
    root = tempfile.mkdtemp(prefix="delegator-contract-")
    try:
        write_surface(root, replacements)
        for rel in omitted or ():
            os.remove(os.path.join(root, *rel.split("/")))
        return subprocess.run(
            [sys.executable, "-B", AUDIT, root],
            text=True,
            capture_output=True,
            check=False,
        )
    finally:
        shutil.rmtree(root)


def main():
    good = run_case()
    assert good.returncode == 0, good.stdout + good.stderr

    boundary = run_case({"agents/openai.yaml": "description: external agents only\n"})
    assert boundary.returncode == 1 and "active-turn boundary" in boundary.stdout

    order = run_case(
        {
            "SKILL.md": "\n".join(
                (
                    "# Skill",
                    "While Delegator is active, never use helpers for exploration, review, implementation, or fallback.",
                    "## Mandatory First Command",
                    "afc-route.py",
                    "afc-blast-radius.py",
                    "afc-first-run-config.py --check-only",
                    "",
                )
            )
        }
    )
    assert order.returncode == 1 and "check-only before" in order.stdout

    state = run_case(
        {
            "references/session-bootstrap-gate.md": (
                "# Bootstrap\nRun once per project regardless of routing. "
                "Use `.agent-inbox/AGENT_ROSTER.md`.\n"
            )
        }
    )
    assert state.returncode == 1 and "canonical roster state" in state.stdout

    runtime = run_case({"scripts/afc-first-run-config.py": 'print("NOT_CONFIGURED")\n'})
    assert runtime.returncode == 1 and "lacks cmd_check_only" in runtime.stdout

    missing = run_case(omitted=("agents/openai.yaml",))
    assert missing.returncode == 1 and "required surface is missing" in missing.stdout

    wrong_flag = run_case({"SKILL.md": GOOD["SKILL.md"].replace("--check-only", "--roster-status")})
    assert wrong_flag.returncode == 1, wrong_flag.stdout + wrong_flag.stderr

    dead_runtime = run_case({"scripts/afc-first-run-config.py": (
        'def cmd_check_only():\n'
        '    if False:\n'
        '        print("next_action: ASK_CAL")\n'
        '    return 1\n'
    )})
    assert dead_runtime.returncode == 1 and "lacks a direct" in dead_runtime.stdout

    print("PASS: 8 Delegator contract fixture cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
