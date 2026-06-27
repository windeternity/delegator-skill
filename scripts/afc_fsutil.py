#!/usr/bin/env python3
"""Shared filesystem utilities for AFC scripts.

Robust atomic file writes and stale-temp hygiene, factored out of the
per-script implementations so every writer (STATUS.md, poll-state, etc.)
shares one Windows-safe behavior instead of reimplementing it with differing
robustness.

Python stdlib only. Python 3.8+ compatible. Windows + POSIX safe.
"""

import os
import time


def safe_remove(path):
    """Remove a file if it exists; never raise."""
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def atomic_write(path, text, retries=5, delay=0.1):
    """Atomically write ``text`` to ``path``.

    Contract:
    - Returns True on success, False on failure.
    - Never corrupts or loses an existing target on failure.
    - Leaves no stale ``.tmp`` after success; cleans up ``.tmp`` on failure.
    - Windows-safe: ``os.replace`` can fail when the target is locked, so it
      retries with exponential backoff, then falls back to a direct write.

    Strategy:
      1. Write ``<path>.tmp`` then ``os.replace`` (atomic), with retries.
      2. If replace keeps failing, fall back to a direct write to the target
         (works when the target is locked for replace but not for write).
      3. If everything fails, clean up the tmp and preserve the prior target.
    """
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(text)
    except OSError:
        safe_remove(tmp)
        return False

    for attempt in range(retries):
        try:
            os.replace(tmp, path)
            return True
        except OSError:
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))

    for attempt in range(retries):
        # Move the existing target aside before a truncating direct write, so a
        # write that fails mid-way (e.g. low disk after open() truncates) cannot
        # leave the target corrupt: on failure restore the backup.
        backup = None
        if os.path.isfile(path):
            backup = path + ".bak"
            safe_remove(backup)
            try:
                os.rename(path, backup)
            except OSError:
                backup = None
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            if backup:
                safe_remove(backup)
            safe_remove(tmp)
            return True
        except OSError:
            if backup:
                try:
                    os.replace(backup, path)
                except OSError:
                    pass
            if attempt < retries - 1:
                time.sleep(delay * (2 ** attempt))

    safe_remove(tmp)
    return False


def sweep_stale_tmp(directory, names=None):
    """Best-effort removal of leftover ``*.tmp`` files in ``directory``.

    A crash or interruption between writing ``<file>.tmp`` and the atomic
    replace can leave a stale temp file behind. Call this on startup so the
    inbox stays clean (the CAL-2 hardening plan requires no stale ``.tmp``).

    If ``names`` is given, only those exact basenames are removed; otherwise
    every ``*.tmp`` in the directory is removed. Returns the count removed.
    """
    removed = 0
    try:
        entries = os.listdir(directory)
    except OSError:
        return 0
    for name in entries:
        if not name.endswith(".tmp"):
            continue
        if names is not None and name not in names:
            continue
        path = os.path.join(directory, name)
        if os.path.isfile(path):
            safe_remove(path)
            if not os.path.isfile(path):
                removed += 1
    return removed
