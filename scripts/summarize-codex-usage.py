#!/usr/bin/env python3
"""Summarize Codex token usage from JSONL event logs.

Python stdlib only. Reads one or more Codex event logs, sums every
`turn.completed.usage` event, and prints per-label and aggregate totals
for input, cached input, uncached input, cache hit ratio, output,
reasoning output, and total (input + output).

``cache_hit_ratio`` is computed as ``cached_input_tokens / input_tokens``.
When ``input_tokens`` is 0, the ratio is reported as ``n/a``.

Usage:
    python -B scripts/summarize-codex-usage.py LABEL=PATH [LABEL=PATH ...]
    python -B scripts/summarize-codex-usage.py --json LABEL=PATH [...]
    python -B scripts/summarize-codex-usage.py --require-label A LABEL_A=PATH [...]

Exit codes:
    0   all inputs parsed, all required labels present
    1   at least one input failed (malformed JSON / no usage / no events)
        OR at least one required label is missing
    2   invalid CLI usage (e.g. LABEL=PATH argument malformed)

The script never invents token counts. Missing optional fields contribute
zero, and the canonical cached-input field is `cached_input_tokens`; the
older `cache_read_input_tokens` is read only as a fallback when the
canonical field is absent. Both keys are NEVER summed together for the
same event. `uncached_input_tokens` is computed as
`max(input_tokens - cached_input_tokens, 0)`. `total_tokens` is
`input_tokens + output_tokens`.
"""

import argparse
import json
import sys


def parse_label_arg(arg):
    """Parse a `LABEL=PATH` argument. Returns (label, path) or raises ValueError."""
    if "=" not in arg:
        raise ValueError(f"Input must be in LABEL=PATH form: {arg!r}")
    label, path = arg.split("=", 1)
    label = label.strip()
    path = path.strip()
    if not label:
        raise ValueError(f"Input label is empty: {arg!r}")
    if not path:
        raise ValueError(f"Input path is empty: {arg!r}")
    return label, path


def empty_usage():
    """Return a fresh usage record with all known fields set to 0."""
    return {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "usage_events": 0,
    }


def summarize_file(path):
    """Parse a Codex JSONL log and return summed usage.

    Returns (usage_dict, error). On success, error is None and usage_dict
    contains the summed values. On failure, usage_dict is None and error
    is a string describing the failure.

    A `turn.completed.usage` event is recognized in either of two forms:

      Flat:     {"type": "turn.completed", "usage": {...}, ...}
      Nested:   {"turn.completed": {"usage": {...}, ...}, ...}

    The flat form matches the standard Codex CLI event log. The nested
    form is accepted as a fallback for callers that wrap the payload.

    Within `usage`, `cached_input_tokens` is the canonical Codex field.
    The older `cache_read_input_tokens` is read only when the canonical
    field is absent. Both keys are never summed together for the same
    event.

    Desktop `token_count` events carry cumulative totals under
    payload.info.total_token_usage. Because these are cumulative, the
    summarizer tracks only the final snapshot rather than summing every
    event, avoiding double-counting.
    """
    usage = empty_usage()
    desktop_cumulative = None  # tracks latest Desktop cumulative snapshot
    desktop_events = 0
    found_any_event = False
    found_usage_event = False
    line_no = 0

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line_no += 1
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    event = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    return None, f"malformed JSON at {path}:{line_no}: {exc.msg}"
                if not isinstance(event, dict):
                    continue
                found_any_event = True

                # Check for Desktop token_count event (cumulative)
                desktop_usage = _extract_desktop_usage(event)
                if isinstance(desktop_usage, dict):
                    desktop_cumulative = desktop_usage
                    desktop_events += 1
                    found_usage_event = True
                    continue

                # Standard turn.completed usage (summed)
                event_usage = _extract_usage(event)
                if not isinstance(event_usage, dict):
                    continue
                found_usage_event = True
                usage["usage_events"] += 1
                for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
                    value = _to_number(event_usage.get(key))
                    if value is not None:
                        usage[key] += value
                cached = _to_number(event_usage.get("cached_input_tokens"))
                if cached is None:
                    cached = _to_number(event_usage.get("cache_read_input_tokens"))
                if cached is not None:
                    usage["cached_input_tokens"] += cached

    except OSError as exc:
        return None, f"could not read {path}: {exc}"

    if not found_any_event:
        return None, f"no events found in {path}"
    if not found_usage_event:
        return None, f"no usage event found in {path}"

    # Merge Desktop cumulative totals (use final snapshot, not sum)
    if desktop_cumulative is not None:
        for key in ("input_tokens", "output_tokens", "reasoning_output_tokens"):
            usage[key] += desktop_cumulative.get(key, 0)
        usage["cached_input_tokens"] += desktop_cumulative.get(
            "cached_input_tokens", 0
        )
        usage["usage_events"] += desktop_events

    return usage, None


def _to_number(value):
    """Return value if it is a usable number, else None. Rejects bool."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _extract_usage(event):
    """Return the `usage` dict for a turn.completed event, or None."""
    if not isinstance(event, dict):
        return None
    if event.get("type") == "turn.completed":
        usage = event.get("usage")
        if isinstance(usage, dict):
            return usage
    nested = event.get("turn.completed")
    if isinstance(nested, dict):
        usage = nested.get("usage")
        if isinstance(usage, dict):
            return usage
    return None


def _extract_desktop_usage(event):
    """Return a usage snapshot from a Codex Desktop token_count event.

    Desktop events carry cumulative totals under payload.info.total_token_usage
    and per-turn deltas under payload.info.last_token_usage.

    The real Codex Desktop JSONL shape wraps the token_count in an event_msg:
        {"type":"event_msg","payload":{"type":"token_count","info":{...}}}

    This function also accepts the unwrapped shape for backward compatibility:
        {"type":"token_count","payload":{"info":{...}}}

    Returns a dict with input_tokens, cached_input_tokens, output_tokens,
    reasoning_output_tokens, or None if the event is not a Desktop token_count.
    """
    if not isinstance(event, dict):
        return None

    # Determine if this is a Desktop token_count event.
    # Real shape: top-level type is "event_msg", payload.type is "token_count".
    # Legacy shape: top-level type is "token_count".
    top_type = event.get("type")
    payload = event.get("payload")
    if not isinstance(payload, dict):
        return None

    is_desktop = False
    if top_type == "event_msg" and payload.get("type") == "token_count":
        is_desktop = True
    elif top_type == "token_count":
        is_desktop = True

    if not is_desktop:
        return None

    info = payload.get("info")
    if not isinstance(info, dict):
        return None
    total = info.get("total_token_usage")
    if not isinstance(total, dict):
        return None

    result = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
    }

    # Use cumulative totals for input and output
    result["input_tokens"] = _to_number(total.get("input_tokens")) or 0
    result["output_tokens"] = _to_number(total.get("output_tokens")) or 0
    result["reasoning_output_tokens"] = (
        _to_number(total.get("reasoning_output_tokens")) or 0
    )

    # Read cached input directly from cumulative total if present.
    # Desktop may include cached_input_tokens in total_token_usage.
    cached = _to_number(total.get("cached_input_tokens"))
    if cached is not None:
        result["cached_input_tokens"] = cached

    return result


def merge_usage(target, source):
    """Merge a per-label usage into an aggregate usage in-place."""
    for key in target:
        target[key] += source.get(key, 0)
    return target


def compute_uncached(usage):
    """Compute uncached input, clamped for anomalous provider values."""
    return max(usage["input_tokens"] - usage["cached_input_tokens"], 0)


def compute_cache_hit_ratio(usage):
    """Compute cache hit ratio as cached_input_tokens / input_tokens.

    Returns the ratio as a float, or the string "n/a" if input_tokens is 0.
    """
    if usage["input_tokens"] == 0:
        return "n/a"
    return usage["cached_input_tokens"] / usage["input_tokens"]


def per_label_view(usage):
    """Return the public output view of one usage record."""
    return {
        "input_tokens": usage["input_tokens"],
        "cached_input_tokens": usage["cached_input_tokens"],
        "uncached_input_tokens": compute_uncached(usage),
        "cache_hit_ratio": compute_cache_hit_ratio(usage),
        "output_tokens": usage["output_tokens"],
        "reasoning_output_tokens": usage["reasoning_output_tokens"],
        "total_tokens": usage["input_tokens"] + usage["output_tokens"],
        "usage_events": usage["usage_events"],
    }


def format_text(per_label, aggregate, missing_required, errors):
    """Format a human-readable text report."""
    out = []
    for label, usage in per_label.items():
        ratio = compute_cache_hit_ratio(usage)
        ratio_str = f"{ratio:.2%}" if isinstance(ratio, float) else ratio
        out.append(f"=== {label} ===")
        out.append(f"  input:           {usage['input_tokens']}")
        out.append(f"  cached input:    {usage['cached_input_tokens']}")
        out.append(f"  uncached input:  {compute_uncached(usage)}")
        out.append(f"  cache hit ratio: {ratio_str}")
        out.append(f"  output:          {usage['output_tokens']}")
        out.append(f"  reasoning out:   {usage['reasoning_output_tokens']}")
        out.append(f"  total:           {usage['input_tokens'] + usage['output_tokens']}")
        out.append(f"  usage events:    {usage['usage_events']}")
        out.append("")
    agg_ratio = compute_cache_hit_ratio(aggregate)
    agg_ratio_str = f"{agg_ratio:.2%}" if isinstance(agg_ratio, float) else agg_ratio
    out.append("=== aggregate ===")
    out.append(f"  input:           {aggregate['input_tokens']}")
    out.append(f"  cached input:    {aggregate['cached_input_tokens']}")
    out.append(f"  uncached input:  {compute_uncached(aggregate)}")
    out.append(f"  cache hit ratio: {agg_ratio_str}")
    out.append(f"  output:          {aggregate['output_tokens']}")
    out.append(f"  reasoning out:   {aggregate['reasoning_output_tokens']}")
    out.append(f"  total:           {aggregate['input_tokens'] + aggregate['output_tokens']}")
    out.append(f"  usage events:    {aggregate['usage_events']}")
    if missing_required or errors:
        out.append("")
        if errors:
            out.append("errors:")
            for label, path, error in errors:
                out.append(f"  - {label} ({path}): {error}")
        if missing_required:
            out.append("missing required labels: " + ", ".join(sorted(missing_required)))
    return "\n".join(out)


def format_json(per_label, aggregate, missing_required, errors):
    """Format a machine-readable JSON report."""
    result = {
        "per_label": {
            label: per_label_view(usage) for label, usage in per_label.items()
        },
        "aggregate": per_label_view(aggregate),
        "missing_required_labels": sorted(missing_required),
        "errors": [
            {"label": label, "path": path, "message": error}
            for label, path, error in errors
        ],
    }
    return json.dumps(result, indent=2, sort_keys=True)


def main():
    parser = argparse.ArgumentParser(
        description="Summarize Codex token usage from JSONL event logs."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more LABEL=PATH pairs pointing at Codex JSONL event logs.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--require-label",
        action="append",
        default=[],
        help="Repeatable. Exit nonzero if any required label is absent from inputs.",
    )
    args = parser.parse_args()

    per_label = {}
    aggregate = empty_usage()
    errors = []

    for arg in args.inputs:
        try:
            label, path = parse_label_arg(arg)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        usage, error = summarize_file(path)
        if error is not None:
            errors.append((label, path, error))
            continue
        if label in per_label:
            merge_usage(per_label[label], usage)
        else:
            per_label[label] = usage
        merge_usage(aggregate, usage)

    seen_labels = set(per_label)
    missing_required = [
        label for label in args.require_label if label not in seen_labels
    ]

    if args.json:
        print(format_json(per_label, aggregate, missing_required, errors))
    else:
        print(format_text(per_label, aggregate, missing_required, errors))

    if errors or missing_required:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
