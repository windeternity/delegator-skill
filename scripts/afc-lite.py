#!/usr/bin/env python3
"""Generate a no-inbox handoff for an approved low-risk LITE task."""

import argparse
import json
import os
import sys

from afc_roster import format_roster_block, maybe_warn_roster, require_usable_roster
from afc_routing import evaluate_route


def yes_no(value):
    lowered = value.strip().lower()
    if lowered not in {"yes", "no"}:
        raise argparse.ArgumentTypeError("expected yes or no")
    return lowered


def build_parser():
    parser = argparse.ArgumentParser(
        description="Create a compact worker handoff without the full inbox protocol."
    )
    parser.add_argument("--agent", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--inbox")
    parser.add_argument("--task", required=True)
    parser.add_argument("--allow-files", required=True)
    parser.add_argument("--validation", default="none")
    parser.add_argument("--language", choices=("en", "zh"), default="en")
    parser.add_argument("--estimated-direct-minutes", type=int, required=True)
    parser.add_argument("--external-worker-required", type=yes_no, required=True)
    parser.add_argument("--semantic-change", type=yes_no, required=True)
    parser.add_argument("--json", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()
    route = evaluate_route({
        "estimated_direct_minutes": args.estimated_direct_minutes,
        "independent_workstreams": 1,
        "smallest_workstream_minutes": args.estimated_direct_minutes,
        "specialized_capability": "no",
        "high_risk_independent_review": "no",
        "external_worker_required": args.external_worker_required,
        "semantic_change": args.semantic_change,
        "expected_rounds": 1,
        "context_bytes": len(args.task.encode("utf-8")),
        "requested_mode": "lite",
    })
    if route["decision"] != "LITE":
        print(
            "error: lite handoff refused; route decision is {}".format(
                route["decision"]
            ),
            file=sys.stderr,
        )
        for reason in route["reasons"]:
            print("error: {}".format(reason), file=sys.stderr)
        return 1

    workspace = os.path.abspath(args.workspace)
    inbox = os.path.abspath(args.inbox or os.path.join(workspace, ".agent-inbox"))
    if not os.path.isdir(inbox):
        print(
            "error: lite handoff refused; roster inbox not found: {}".format(inbox),
            file=sys.stderr,
        )
        return 1
    ok, status = require_usable_roster(inbox, agent_name=args.agent)
    maybe_warn_roster(status)
    if not ok:
        print(format_roster_block(status), file=sys.stderr)
        return 1
    if args.language == "zh":
        handoff = "\n".join([
            "你是 {}。".format(args.agent),
            "把这个现有工作区作为项目打开：{}。".format(workspace),
            "任务：{}".format(args.task),
            "只允许修改：{}。".format(args.allow_files),
            "验证：{}。".format(args.validation),
            "不要创建任务单、状态板或事件日志。不要 commit/push。",
            "完成后只回复：改动文件、验证结果、阻塞项。",
        ])
    else:
        handoff = "\n".join([
            "You are {}.".format(args.agent),
            "Open this existing workspace as the project: {}.".format(workspace),
            "Task: {}".format(args.task),
            "Allowed files only: {}.".format(args.allow_files),
            "Validation: {}.".format(args.validation),
            "Do not create task/status/event files. Do not commit or push.",
            "Reply only with changed files, validation result, and blockers.",
        ])

    if args.json:
        print(json.dumps({
            "mode": "LITE",
            "workspace": workspace,
            "route": route,
            "handoff": handoff,
        }, indent=2, ensure_ascii=False))
    else:
        print(handoff)
    return 0


if __name__ == "__main__":
    sys.exit(main())
