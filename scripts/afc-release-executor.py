#!/usr/bin/env python3
"""Deterministic release executor for bounded commit/push chores.

This is not an LLM worker. It implements the J6 Release-Operator hard gates for
the simple post-GO path where the coordinator has already reviewed the report
and approved an exact commit message.

Usage:
    python -B scripts/afc-release-executor.py --task <TASK_FILE> --commit-message "docs: update x"
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

try:
    from afc_frontmatter import parse_frontmatter_flat
except ModuleNotFoundError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from afc_frontmatter import parse_frontmatter_flat


SECRET_PATTERNS = [
    (
        re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*([^\s]+)"),
        lambda m: "{}=<redacted>".format(m.group(1)),
    ),
    (
        re.compile(r"(?i)(bearer)\s+[A-Za-z0-9._~+/=-]+"),
        lambda m: "{} <redacted>".format(m.group(1)),
    ),
    (
        re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
        lambda m: "<redacted-secret>",
    ),
]


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def redact_text(text):
    redacted = text
    for pattern, replacement in SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def run_git(workspace, args):
    result = subprocess.run(
        ["git"] + args,
        cwd=workspace,
        capture_output=True,
        text=True,
        shell=False,
    )
    return {
        "argv": ["git"] + args,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def parse_task(path):
    data, err = parse_frontmatter_flat(path, strict=False)
    if err or not data:
        return None, err or "missing task frontmatter"
    if data.get("schema") != "agent-file-coordination/task":
        return None, "not a task file"
    return data, None


def parse_report(path):
    data, err = parse_frontmatter_flat(path, strict=False)
    if err or not data:
        return None, err or "missing report frontmatter"
    if data.get("schema") != "agent-file-coordination/report":
        return None, "not a report file"
    return data, None


def split_scope(raw):
    return [part.strip().replace("\\", "/").rstrip("/") for part in re.split(r"[;,]", raw or "") if part.strip()]


def whole_workspace_scope(scope):
    normalized = scope.strip().replace("\\", "/").rstrip("/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized in {".", "*", "**"}


def _strip_dot_slash(value):
    """Strip a single leading './' prefix, not a character set.

    str.lstrip('./') treats the argument as the set {'.', '/'} and would also
    eat a lone leading '.' or '/' (e.g. '.secret' -> 'secret'), silently
    over-matching dotfiles. Only the './' relative-path prefix is intended.
    """
    normalized = value.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def within_any(path, scopes):
    normalized = _strip_dot_slash(path)
    for scope in scopes:
        if whole_workspace_scope(scope):
            continue
        scope = _strip_dot_slash(scope)
        if normalized == scope or normalized.startswith(scope.rstrip("/") + "/"):
            return True
    return False


def changed_files(workspace):
    diff = run_git(workspace, ["diff", "--name-only", "HEAD", "--"])
    untracked = run_git(workspace, ["ls-files", "--others", "--exclude-standard"])
    files = []
    for result in (diff, untracked):
        if result["exit_code"] != 0:
            return None, result
        for line in result["stdout"].splitlines():
            line = line.strip()
            if line.replace("\\", "/").startswith(".agent-inbox/"):
                continue
            if line and line not in files:
                files.append(line)
    return files, None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Deterministic bounded git release executor.")
    parser.add_argument("--task", required=True, help="task file path")
    parser.add_argument("--report", help="report file path; defaults to task report_path")
    parser.add_argument("--commit-message", required=True)
    parser.add_argument("--coordinator-go", action="store_true")
    parser.add_argument("--execute", action="store_true", help="actually commit")
    parser.add_argument("--push", action="store_true", help="push after commit")
    parser.add_argument("--push-approved", action="store_true")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    task_path = os.path.abspath(args.task)
    task, err = parse_task(task_path)
    if err:
        print("error: {}".format(err), file=sys.stderr)
        return 1
    workspace = os.path.abspath(task.get("workspace.path", ""))
    if not os.path.isdir(workspace):
        print("error: workspace not found: {}".format(workspace), file=sys.stderr)
        return 1
    if str(task.get("permission_scope.commit_push", "")).strip().lower() != "approved":
        print("error: task must set permission_scope.commit_push: approved", file=sys.stderr)
        return 1
    if str(task.get("permission_scope.destructive_actions", "")).strip().lower() not in {"no", "false"}:
        print("error: destructive_actions must remain no", file=sys.stderr)
        return 1
    if args.execute and not args.coordinator_go:
        print("error: --execute requires --coordinator-go", file=sys.stderr)
        return 1
    if args.push and not args.push_approved:
        print("error: --push requires --push-approved", file=sys.stderr)
        return 1

    report_path = args.report or task.get("report_path", "")
    if not os.path.isabs(report_path):
        normalized_report = report_path.replace("\\", "/")
        if normalized_report.startswith(".agent-inbox/"):
            report_path = os.path.abspath(os.path.join(workspace, normalized_report))
        else:
            report_path = os.path.abspath(os.path.join(workspace, report_path))
    report, err = parse_report(report_path)
    if err:
        print("error: report-before-commit failed: {}".format(err), file=sys.stderr)
        return 1
    if report.get("task_id") != task.get("task_id"):
        print("error: report task_id does not match task", file=sys.stderr)
        return 1

    scopes = split_scope(task.get("workspace.locked_files_or_areas", ""))
    if not scopes:
        print("error: task missing locked_files_or_areas allowlist", file=sys.stderr)
        return 1
    invalid_scopes = [scope for scope in scopes if whole_workspace_scope(scope)]
    if invalid_scopes:
        print(
            "error: whole-workspace locked_files_or_areas scope is not allowed: {}".format(
                ", ".join(invalid_scopes)
            ),
            file=sys.stderr,
        )
        return 1
    files, git_error = changed_files(workspace)
    if git_error:
        print("error: git failed: {}".format(git_error["stderr"][:300]), file=sys.stderr)
        return 1
    outside = [path for path in files if not within_any(path, scopes)]
    if outside:
        print("error: changed files outside allowlist: {}".format(", ".join(outside)), file=sys.stderr)
        return 1

    branch_result = run_git(workspace, ["branch", "--show-current"])
    branch = branch_result["stdout"].strip()
    expected_branch = args.branch or task.get("workspace.branch", "").strip()
    if expected_branch and expected_branch not in {"<BRANCH_NAME>", "unknown"} and branch != expected_branch:
        print("error: branch mismatch: current={}, expected={}".format(branch, expected_branch), file=sys.stderr)
        return 1

    artifact_dir = os.path.join(
        os.path.dirname(report_path),
        "artifacts",
        "release-executor",
        task.get("task_id", "task"),
    )
    os.makedirs(artifact_dir, exist_ok=True)
    log_path = os.path.join(artifact_dir, "release-executor.log")
    log_entries = []

    state = "DRY_RUN"
    commit_hash = None
    if args.execute:
        if not files:
            print("error: no changed files to commit", file=sys.stderr)
            return 1
        add_result = run_git(workspace, ["add", "--"] + files)
        log_entries.append(add_result)
        if add_result["exit_code"] != 0:
            state = "FAILED"
        else:
            commit_result = run_git(workspace, ["commit", "-m", args.commit_message])
            log_entries.append(commit_result)
            if commit_result["exit_code"] != 0:
                state = "FAILED"
            else:
                rev = run_git(workspace, ["rev-parse", "--short", "HEAD"])
                log_entries.append(rev)
                commit_hash = rev["stdout"].strip() if rev["exit_code"] == 0 else None
                state = "COMMITTED"
                if args.push:
                    push_result = run_git(workspace, ["push", args.remote, branch])
                    log_entries.append(push_result)
                    state = "PUSHED" if push_result["exit_code"] == 0 else "FAILED"

    with open(log_path, "w", encoding="utf-8", newline="\n") as handle:
        for entry in log_entries:
            handle.write("$ {}\n".format(" ".join(entry["argv"])))
            handle.write(redact_text(entry["stdout"]))
            handle.write(redact_text(entry["stderr"]))
            handle.write("\nexit={}\n\n".format(entry["exit_code"]))

    payload = {
        "state": state,
        "task_id": task.get("task_id"),
        "branch": branch,
        "files": files,
        "commit": commit_hash,
        "commit_message": args.commit_message,
        "log_path": log_path.replace("\\", "/"),
        "executed": bool(args.execute),
        "pushed": state == "PUSHED",
        "created_at": utc_now_iso(),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(
            "RELEASE_STATUS state={state} task_id={task_id} branch={branch} "
            "files={count} commit={commit} log={log}".format(
                state=payload["state"],
                task_id=payload["task_id"],
                branch=payload["branch"],
                count=len(files),
                commit=payload["commit"] or "-",
                log=payload["log_path"],
            )
        )
    return 0 if state != "FAILED" else 1


if __name__ == "__main__":
    sys.exit(main())
