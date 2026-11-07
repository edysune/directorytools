"""Human-readable run report (also the cron digest source)."""

from __future__ import annotations

from .config import Config
from .logs import Redactor
from .models import RunReport


def human(n: int) -> str:
    n = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{int(n)} {unit}" if unit == "B" else f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} TB"


def _paths(items, redactor) -> str:
    return ", ".join(redactor.display(f.path) for f in items)


def render(cfg: Config, report: RunReport, redactor: Redactor,
           performed=None, state=None) -> str:
    if cfg.dry_run:
        mode = "DRY-RUN (no modifications)"
    elif cfg.allow_delete:
        mode = "DELETION ENABLED (dry-run off, allow-delete on)"
    else:
        mode = "dry-run OFF but allow-delete OFF -> no deletion (guard)"
    L = [
        "================ dedup_cleaner run report ================",
        f"mode            : {mode}",
        f"root            : {redactor.display(cfg.root)}",
        f"preferred       : {len(cfg.preferred)} path(s);  excluded: {len(cfg.excluded)} path(s)",
        f"scanned files   : {report.scanned_files}  ({human(report.scanned_bytes)})",
        f"dup groups      : {report.groups_examined}",
        f"files hashed    : {report.hashed_files}",
        f"issues found    : {report.issues_identified()}  "
        f"(resolved {report.resolved_count()}, skipped/ambiguous {report.skip_count()})",
        f"space to recover: {human(report.planned_bytes())}",
    ]
    if report.stopped_by_cap:
        L.append(f"note            : stopped early (hit max_changes = {cfg.max_changes})")
    if state is not None:
        L.append(f"state rows      : {len(state)}")

    if report.actions:
        L.append("---------------- actions ----------------")
        for a in report.actions:
            if a.kind == "DEDUP_KEEP":
                L.append(f"  KEEP  {redactor.display(a.keeper.path)}")
                L.append(f"    -> remove {len(a.removed)}: {_paths(a.removed, redactor)}"
                         f"   [{a.reason}]")
            elif a.kind == "DEDUP_SKIP":
                L.append(f"  SKIP  {_paths(a.kept or a.removed, redactor)}   [{a.reason}]")
            elif a.kind == "REMOVE_BAD_TYPE":
                L.append(f"  BAD   {_paths(a.removed, redactor)}   [{a.reason}]")
    if performed:
        L.append("---------------- performed ----------------")
        L += ["  " + p for p in performed]
    if report.warnings:
        L.append("---------------- warnings ----------------")
        L += ["  " + w for w in report.warnings]
    if report.errors:
        L.append("---------------- errors ----------------")
        L += ["  " + e for e in report.errors]
    L.append("=====================================================")
    return "\n".join(L)
