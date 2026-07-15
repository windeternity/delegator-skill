"""Shared constants for afc-* scripts.

Single source of truth for status and byte-budget values that were
previously copy-pasted across scripts. Keep this module stdlib-only and
importable from any afc-* script (direct execution puts scripts/ on
sys.path automatically; scripts that may be imported add it explicitly).
"""

# Terminal task statuses. Membership-tested as `status in CLOSED_STATUSES`
# and rendered via sorted(); a frozenset is immutable and safe to share.
# When the validator's status enum in afc_inbox_validation.py changes,
# update this set to match.
CLOSED_STATUSES = frozenset({
    "CLOSED_GO",
    "CLOSED_PARTIAL",
    "CLOSED_RED",
    "CANCELLED",
    "SUPERSEDED",
})

# Inline context budgets, in bytes. An override needs an explicit recorded
# reason (see references/delegation-routing-v1.md).
TASK_BUDGET_BYTES = 4 * 1024
REPORT_BUDGET_BYTES = 3 * 1024
REVIEW_REPORT_BUDGET_BYTES = 5 * 1024
