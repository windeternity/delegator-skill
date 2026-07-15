#!/usr/bin/env python3
"""Probe local headless CLI workers for CAL-3.

This helper is intentionally conservative: it only checks whether known CLI
entry points exist and expose a non-interactive command shape. It does not call
an LLM, mutate project files, or install anything.

Usage:
    python -B scripts/afc-cal3-probe.py --inbox .agent-inbox [--write]
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone


SCHEMA = "agent-file-coordination/cal3-invoke-recipes"
DEFAULT_TIMEOUT = 10


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_probe(argv, timeout=DEFAULT_TIMEOUT):
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
    except FileNotFoundError:
        return {"ok": False, "exit_code": None, "output": "command not found"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit_code": None, "output": "probe timed out"}

    output = (result.stdout or "") + (result.stderr or "")
    output = " ".join(output.split())[:500]
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "output": output,
    }


def existing_path(path):
    if path and os.path.isfile(path):
        return os.path.abspath(path)
    return None


def looks_like_npm_shim(path):
    lowered = (path or "").replace("\\", "/").lower()
    return (
        lowered.endswith("/codex.cmd")
        or lowered.endswith("/codex.ps1")
        or "/npm-global/" in lowered
        or "/node_modules/" in lowered
    )


def powershell_codex_desktop_path():
    if os.name != "nt":
        return None
    command = (
        "$cmd = Get-Command Get-CodexDesktopExe -ErrorAction SilentlyContinue; "
        "if ($cmd) { $path = Get-CodexDesktopExe; if ($path) { Write-Output $path } }"
    )
    for shell_name in ("pwsh", "powershell"):
        shell_path = shutil.which(shell_name)
        if not shell_path:
            continue
        try:
            result = subprocess.run(
                [shell_path, "-Command", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=DEFAULT_TIMEOUT,
                shell=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0:
            continue
        for line in (result.stdout or "").splitlines():
            candidate = existing_path(line.strip().strip('"'))
            if candidate and not looks_like_npm_shim(candidate):
                return candidate
    return None


def find_codex_desktop_path():
    override = existing_path(os.environ.get("AFC_CAL3_CODEX_EXE", ""))
    if override:
        return override

    from_profile = powershell_codex_desktop_path()
    if from_profile:
        return from_profile

    candidates = []
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        # Codex desktop installs under a version-hash subdir that changes on
        # auto-update; sort newest-first so we resolve the current build instead
        # of a stale hash dir left behind by a previous version.
        hits = glob.glob(os.path.join(local_appdata, "**", "codex.exe"), recursive=True)
        hits.sort(
            key=lambda p: os.path.getmtime(p) if os.path.isfile(p) else 0.0,
            reverse=True,
        )
        candidates.extend(hits)

    windows_apps = os.path.join(
        os.environ.get("USERPROFILE", ""),
        "AppData",
        "Local",
        "Microsoft",
        "WindowsApps",
        "codex.exe",
    )
    candidates.append(windows_apps)

    for candidate in candidates:
        path = existing_path(candidate)
        if path and not looks_like_npm_shim(path):
            return path

    for name in ("codex.exe", "codex"):
        path = shutil.which(name)
        if path and not looks_like_npm_shim(path):
            return os.path.abspath(path)
    return None


def find_node_cli_exe(command_name, package_path):
    override = existing_path(os.environ.get("AFC_CAL3_{}_EXE".format(command_name.upper()), ""))
    if override:
        return override
    path = shutil.which(command_name)
    if not path:
        return None
    resolved = os.path.abspath(path)
    lowered = resolved.replace("\\", "/").lower()
    if os.name == "nt" and (lowered.endswith(".ps1") or lowered.endswith(".cmd")):
        candidate = os.path.join(os.path.dirname(resolved), package_path)
        exe = existing_path(candidate)
        if exe:
            return exe
    return resolved


def path_is_within(path, parent):
    try:
        return os.path.commonpath(
            [os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(parent))]
        ) == os.path.normcase(os.path.abspath(parent))
    except ValueError:
        return False


def codex_network_access():
    raw = os.environ.get("AFC_CAL3_CODEX_NETWORK_ACCESS", "").strip().lower()
    if raw in {"1", "true", "yes", "allowed"}:
        return "allowed"
    return "none"


def codex_recipe(path):
    return {
        "tool": "codex",
        "path": path,
        "available": True,
        "argv": [
            path,
            "exec",
            "-C",
            "{workspace}",
            "-s",
            "{codex_sandbox}",
            "{prompt}",
        ],
        "cwd": "{workspace}",
        "sandbox": "workspace-write",
        "timeout_seconds": 1800,
        "supports_resume": False,
        "capability": {
            "modify_source": True,
            "run_commands": "bounded",
            "network_access": codex_network_access(),
            "commit_push": "no",
        },
        "approval_patterns": [
            "APPROVAL REQUIRED",
            "requires approval",
            "permission prompt",
            "stdin is not a terminal",
        ],
        "profile_args": {
            # CAL-3 readonly means source-readonly, not filesystem-readonly:
            # workers still need to write their report under .agent-inbox.
            "cal3-readonly": {"codex_sandbox": "workspace-write"},
            "cal3-bounded-edit": {"codex_sandbox": "workspace-write"},
            "cal3-local-autonomous": {"codex_sandbox": "workspace-write"},
            "cal3-local-autonomous-high": {"codex_sandbox": "workspace-write"},
            "cal3-network-readonly": {"codex_sandbox": "workspace-write"},
            "cal3-network-work": {"codex_sandbox": "workspace-write"},
            "cal3-approved-commit": {"codex_sandbox": "workspace-write"},
            "cal3-release-gated": {"codex_sandbox": "workspace-write"},
        },
    }


def codex_launcher_recipe(launcher):
    """Codex recipe that runs through a user-provided launcher script.

    Set AFC_CAL3_CODEX_LAUNCHER to a script that selects the real codex.exe and
    sets any provider environment (CODEX_HOME, API keys) -- e.g. a wrapper that
    points Codex at a third-party model. This keeps machine-specific paths and
    credentials out of the recipe and the repo. subprocess(shell=False) cannot
    run .ps1/.cmd directly, so they are fronted with powershell.exe / cmd.exe.
    """
    lower = launcher.lower()
    if lower.endswith(".ps1"):
        prefix = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", launcher]
    elif lower.endswith(".cmd") or lower.endswith(".bat"):
        prefix = ["cmd", "/c", launcher]
    else:
        prefix = [launcher]
    recipe = codex_recipe(launcher)
    recipe["backend"] = "launcher"
    recipe["launcher"] = launcher
    recipe["argv"] = prefix + [
        "exec",
        "--skip-git-repo-check",
        "-C",
        "{workspace}",
        "-s",
        "{codex_sandbox}",
        "{prompt}",
    ]
    return recipe


def parse_aliases(raw):
    aliases = []
    for part in re.split(r"[;,]", raw or ""):
        alias = part.strip()
        if alias and alias not in aliases:
            aliases.append(alias)
    return aliases


def codex_agent_aliases(launcher=""):
    aliases = parse_aliases(os.environ.get("AFC_CAL3_CODEX_ALIASES", ""))
    base = os.path.basename(launcher or "").lower()
    if launcher and ("codex3p" in base or "3p" in base) and "codex3p" not in aliases:
        aliases.append("codex3p")
    return aliases


def mimo_recipe(path):
    report_instruction = (
        "{prompt}\n\n"
        "Mimo AFC report compatibility: write the final answer only to the report path. "
        "Use schema: agent-file-coordination/report and the exact frontmatter keys from "
        "the prompt. evidence_trust, guardrails, and validation must be nested YAML "
        "mappings. Do not invent status, role, permission_scope, evidence_trust.level, "
        "or validation.status fields."
    )
    return {
        "tool": "mimo",
        "path": path,
        "available": True,
        "argv": [
            path,
            "run",
            "--dir",
            "{workspace}",
            "--dangerously-skip-permissions",
            report_instruction,
        ],
        "cwd": "{workspace}",
        "sandbox": "none",
        "timeout_seconds": 1800,
        "supports_resume": False,
        "capability": {
            "modify_source": True,
            "run_commands": "bounded",
            "network_access": "none",
            "commit_push": "no",
        },
        "approval_patterns": [
            "approval",
            "permission",
            "confirm",
            "权限",
            "审批",
        ],
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


def claude_recipe(path):
    return {
        "tool": "claude",
        "path": path,
        "available": True,
        "argv": [
            path,
            "-p",
            "--dangerously-skip-permissions",
            "--output-format",
            "text",
            "{prompt}",
        ],
        "cwd": "{workspace}",
        "sandbox": "none",
        "timeout_seconds": 1800,
        "supports_resume": False,
        "capability": {
            "modify_source": True,
            "run_commands": "bounded",
            "network_access": "none",
            "commit_push": "no",
        },
        "approval_patterns": [
            "APPROVAL REQUIRED",
            "requires approval",
            "permission",
            "confirm",
        ],
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


def opencode_recipe(path):
    return {
        "tool": "opencode",
        "path": path,
        "available": True,
        "argv": [
            path,
            "run",
            "--dir",
            "{workspace}",
            "--dangerously-skip-permissions",
            "{prompt}",
        ],
        "cwd": "{workspace}",
        "sandbox": "none",
        "timeout_seconds": 1800,
        "supports_resume": False,
        "capability": {
            "modify_source": True,
            "run_commands": "bounded",
            "network_access": "none",
            "commit_push": "no",
        },
        "approval_patterns": [
            "APPROVAL REQUIRED",
            "requires approval",
            "permission",
            "confirm",
        ],
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


def probe_tool(name, path, help_args, recipe_builder):
    if not path:
        return {
            "tool": name,
            "available": False,
            "reason": "not found on PATH",
        }, None

    version = run_probe([path, "--version"])
    help_result = run_probe([path] + help_args)
    recipe = recipe_builder(path)
    recipe["version_probe"] = version
    recipe["headless_probe"] = help_result
    return {
        "tool": name,
        "available": help_result["ok"],
        "path": path,
        "version_probe": version,
        "headless_probe": help_result,
    }, recipe if help_result["ok"] else None


def build_recipes():
    probes = []
    recipes = {}
    agent_recipes = {}

    codex_launcher = os.environ.get("AFC_CAL3_CODEX_LAUNCHER", "").strip()
    if codex_launcher:
        if os.path.isfile(codex_launcher):
            # Personalized backend: route codex through the user's launcher script
            # (handles real exe resolution + provider env). Path stays machine-local.
            recipes["codex"] = codex_launcher_recipe(codex_launcher)
            probes.append({
                "tool": "codex",
                "available": True,
                "backend": "launcher",
                "launcher": codex_launcher,
                "path": codex_launcher,
            })
            for alias in codex_agent_aliases(codex_launcher):
                agent_recipes[alias] = "codex"
        else:
            # A configured launcher is an explicit backend choice. Fail closed
            # instead of silently falling back to native codex.
            probes.append({
                "tool": "codex",
                "available": False,
                "backend": "launcher",
                "reason": "AFC_CAL3_CODEX_LAUNCHER not found: {}".format(codex_launcher),
            })
    else:
        codex_path = find_codex_desktop_path()
        probe, recipe = probe_tool("codex", codex_path, ["exec", "--help"], codex_recipe)
        probe["backend"] = "native"
        probes.append(probe)
        if recipe:
            recipes["codex"] = recipe
            for alias in codex_agent_aliases():
                agent_recipes[alias] = "codex"

    probe, recipe = probe_tool("mimo", shutil.which("mimo"), ["run", "--help"], mimo_recipe)
    probes.append(probe)
    if recipe:
        recipes["mimo"] = recipe

    probe, recipe = probe_tool("claude", shutil.which("claude"), ["--help"], claude_recipe)
    probes.append(probe)
    if recipe:
        recipes["claude"] = recipe

    opencode_path = find_node_cli_exe(
        "opencode",
        os.path.join("node_modules", "opencode-ai", "bin", "opencode.exe"),
    )
    probe, recipe = probe_tool("opencode", opencode_path, ["run", "--help"], opencode_recipe)
    probes.append(probe)
    if recipe:
        recipes["opencode"] = recipe

    return {
        "schema": SCHEMA,
        "schema_version": "0.1.0",
        "generated_at": utc_now_iso(),
        "default_permission_profile": "cal3-bounded-edit",
        "agent_recipes": agent_recipes,
        "recipes": recipes,
        "probes": probes,
        "notes": [
            "Map project-local agent names to recipe ids in agent_recipes.",
            "Bind personal aliases such as codex3p through agent_recipes or "
            "AFC_CAL3_CODEX_LAUNCHER; do not hardcode them in the dispatcher.",
            "Set AFC_CAL3_CODEX_ALIASES=alias1,alias2 before probing to bind "
            "project-local codex aliases to the codex recipe.",
            "Codex recipes default network_access to none; set "
            "AFC_CAL3_CODEX_NETWORK_ACCESS=allowed only after local Codex "
            "workspace-write network access is explicitly configured.",
            "External SQLite/Chroma/vector-store data dirs outside workspace "
            "must be authorized in local Codex writable_roots; recipes do not "
            "auto-expand filesystem write boundaries.",
            "Keep this file in .agent-inbox; do not copy it into a skill package.",
            "codex backend: set AFC_CAL3_CODEX_LAUNCHER to a launcher script "
            "(e.g. a third-party-model wrapper) to route codex through it; "
            "otherwise the newest native codex.exe is used. Each codex probe "
            "reports its 'backend' (native | launcher).",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Probe local headless CLI workers for CAL-3."
    )
    parser.add_argument("--inbox", required=True, help="agent-inbox directory")
    parser.add_argument(
        "--write",
        action="store_true",
        help="write .agent-inbox/invoke-recipes.json",
    )
    parser.add_argument(
        "--output",
        help="explicit recipe output path; defaults to <inbox>/invoke-recipes.json",
    )
    args = parser.parse_args(argv)

    inbox = os.path.abspath(args.inbox)
    if not os.path.isdir(inbox):
        print("error: inbox directory not found: {}".format(inbox), file=sys.stderr)
        return 1

    data = build_recipes()
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    if args.write:
        output = args.output or os.path.join(inbox, "invoke-recipes.json")
        output = os.path.abspath(output)
        if not path_is_within(output, inbox):
            print(
                "error: recipe output must stay inside the inbox",
                file=sys.stderr,
            )
            return 1
        with open(output, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print("Wrote {}".format(output))
        print("CAL3_STATUS state=probe_finished recipes={}".format(
            len(data.get("recipes", {}))
        ))
        return 0

    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
