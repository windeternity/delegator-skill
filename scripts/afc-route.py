#!/usr/bin/env python3
"""Choose DIRECT, LITE, FULL, or SPLIT before creating coordination artifacts."""

import argparse
import json
import sys

from afc_routing import evaluate_route


def yes_no(value):
    lowered = value.strip().lower()
    if lowered not in {"yes", "no"}:
        raise argparse.ArgumentTypeError("expected yes or no")
    return lowered


def build_parser():
    parser = argparse.ArgumentParser(
        description="Deterministic Delegator ROI and granularity gate."
    )
    parser.add_argument("--estimated-direct-minutes", type=int, required=True)
    parser.add_argument("--independent-workstreams", type=int, default=1)
    parser.add_argument("--smallest-workstream-minutes", type=int)
    parser.add_argument("--specialized-capability", type=yes_no, default="no")
    parser.add_argument("--high-risk-independent-review", type=yes_no, default="no")
    parser.add_argument("--external-worker-required", type=yes_no, default="no")
    parser.add_argument("--semantic-change", type=yes_no, default="yes")
    parser.add_argument("--expected-rounds", type=int, default=1)
    parser.add_argument("--context-bytes", type=int, default=0)
    parser.add_argument(
        "--requested-mode",
        choices=("auto", "direct", "lite", "full"),
        default="auto",
    )
    parser.add_argument("--override", type=yes_no, default="no")
    parser.add_argument("--override-reason", default="")
    parser.add_argument(
        "--available-distinct-models",
        type=int,
        default=1,
        help="distinct capable models the roster can bring (MOA gate; default 1=dormant)",
    )
    parser.add_argument(
        "--blast-radius",
        choices=("low", "medium", "high", "unknown"),
        default="unknown",
        help="blast radius of the planned change (default unknown: run "
             "afc-blast-radius.py and pass the result, or the MOA value gate "
             "will not fire)",
    )
    parser.add_argument("--json", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()
    json_mode = args.json
    values = vars(args).copy()
    values.pop("json")
    result = evaluate_route(values)
    if json_mode:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            "{} max_workers={} reason={}".format(
                result["decision"],
                result.get("max_workers", 0),
                ",".join(result["reason_codes"]),
            )
        )
    return 1 if result["decision"] == "INVALID" else 0


if __name__ == "__main__":
    sys.exit(main())
