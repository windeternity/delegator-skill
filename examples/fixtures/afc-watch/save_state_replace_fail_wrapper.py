#!/usr/bin/env python3
"""Wrapper that patches os.replace to always fail, then runs afc-watch.py.

Used to test the direct-write fallback in _save_state.
"""
import importlib.util
import os
import sys

# Patch os.replace BEFORE loading afc-watch module
_orig_replace = os.replace


def _always_fail_replace(src, dst):
    raise OSError("simulated replace failure")


# Keep os.replace patched for the entire execution so _save_state
# falls through to the direct-write fallback.
os.replace = _always_fail_replace

# Import afc-watch module (it will use the patched os.replace)
script_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts")
spec = importlib.util.spec_from_file_location(
    "afc_watch",
    os.path.normpath(os.path.join(script_dir, "afc-watch.py")),
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Run main with original args (os.replace remains patched)
sys.exit(mod.main())
