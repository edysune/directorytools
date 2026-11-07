"""Deletion gate + the (guarded) fix stage.

The real ``os.remove`` code is present and unit-tested, but it only runs when
``Config.deletion_enabled()`` is true — which requires BOTH ``dry_run`` false
AND the independent master switch ``allow_delete`` true. With the shipped
``.env.example`` defaults both are off, so deletion is a no-op by default.
"""

from __future__ import annotations
import os
from typing import List

from .config import Config
from .logs import Redactor
from .models import RunReport


def apply(cfg: Config, report: RunReport, redactor: Redactor, log=print) -> List[str]:
    """Execute any deletions. Returns a list of human lines of what actually
    happened (empty in dry-run / not-enabled)."""
    performed: List[str] = []
    if not cfg.deletion_enabled():
        return performed
    for a in report.actions:
        for f in a.removed:
            try:
                os.remove(f.path)
                performed.append(
                    f"[{a.kind}] removed {redactor.display(f.path)} ({f.size} bytes)")
            except OSError as exc:
                report.errors.append(
                    f"delete failed {redactor.display(f.path)}: {exc}")
    return performed
