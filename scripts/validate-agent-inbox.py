#!/usr/bin/env python3
"""CLI compatibility wrapper for the importable AFC validation core."""

import sys

from afc_inbox_validation import main


if __name__ == "__main__":
    sys.exit(main())
