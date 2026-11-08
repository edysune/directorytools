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
    happened (empty in dry-run / not-enabled).

    Scope: when ``cfg.delete_bad_only`` is set, ONLY ``REMOVE_BAD_TYPE``
    actions execute; dedup-pair deletions (DEDUP_KEEP) are left untouched
    even though deletion is enabled. The master gate still applies either
    way: nothing is removed unless both dry_run is off and allow_delete is on.
    """
    performed: List[str] = []
    if not cfg.deletion_enabled():
        return performed
    for a in report.actions:
        if cfg.delete_bad_only and a.kind != "REMOVE_BAD_TYPE":
            continue
        for f in a.removed:
            try:
                os.remove(f.path)
                performed.append(
                    f"[{a.kind}] removed {redactor.display(f.path)} ({f.size} bytes)")
            except OSError as exc:
                report.errors.append(
                    f"delete failed {redactor.display(f.path)}: {exc}")
    return performed
