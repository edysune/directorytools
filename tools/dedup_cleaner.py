#!/usr/bin/env python3
"""CLI entrypoint (matches the repo's tools/*.py convention).

Usage:
    python tools/dedup_cleaner.py --root /path/to/scan \\
        --preferred /path/a --ignore /path/b --dry-run \\
        --bad-file-types .part --max-changes 10 [flags]

Every flag is optional; env-var defaults (DEDUP_*) are used when the flag is
absent, and both can co-exist with the mounted ``.env`` in docker.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dedup_cleaner.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
