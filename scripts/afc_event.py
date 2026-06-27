#!/usr/bin/env python3
"""Shared helpers for compact, attributable AFC events."""

import json
import os
from datetime import datetime, timezone


ATTRIBUTION_FIELDS = (
    "trace_id",
    "coordinator_thread_id",
    "coordinator_root_thread_id",
)


def utc_now_iso():
    """Return an ISO 8601 UTC timestamp with second precision."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def add_event_context(event, source, phase, occurred_at=None):
    """Add precise time, lifecycle phase, and optional attribution fields."""
    event["occurred_at"] = occurred_at or utc_now_iso()
    event["phase"] = phase
    for field in ATTRIBUTION_FIELDS:
        value = str(source.get(field, "") or "").strip()
        if value:
            event[field] = value
    return event


def append_event_once(events_path, event):
    """Append an event unless its event_id already exists.

    Returns True when appended and False when already present.
    """
    event_id = event.get("event_id")
    if os.path.isfile(events_path):
        try:
            with open(events_path, "r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        existing = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if existing.get("event_id") == event_id:
                        return False
        except OSError:
            pass

    with open(events_path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return True


def report_event_id(task_id, report_mtime):
    """Build a stable ID shared by poll and watch for the same report version."""
    compact_mtime = "".join(ch for ch in report_mtime if ch.isalnum())
    return "evt-{}-report-received-{}".format(task_id, compact_mtime)
