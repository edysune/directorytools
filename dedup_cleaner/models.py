"""Data model for one scan pass: files, dedup decisions, and the run report.

Everything here is a plain data class that needs no filesystem access, which
keeps the rule engine fast to unit-test.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class FileInfo:
    """One file discovered by the scanner (absolute path, basename, size)."""
    name: str          # basename, e.g. "video.mkv"
    path: str          # absolute, OS-normalized path
    size: int          # bytes
    mtime: int = 0     # int seconds, informational only

    def key(self) -> "tuple[str, int]":
        """The identity used to find candidate duplicates: name + byte size."""
        return (self.name, self.size)


@dataclass
class Action:
    """A single dedup/clean decision and what (potentially) happens.

    ``kind`` is one of:
        * ``DEDUP_KEEP``          -- keep ``keeper``, delete the ``removed`` list
        * ``DEDUP_SKIP``          -- ambiguity; nothing deleted (still counted)
        * ``REMOVE_BAD_TYPE``     -- a .part/-like file; delete regardless
      (the actual deletion is gated by ``dry_run`` + ``allow_delete``)

    ``resolved`` is True when the rule picked a keep-and-drop decision
    (actionable); False when it was a skip/ambiguity. Both count toward the
    ``max_changes`` cap (the user wants ambiguous skips counted too).
    """
    kind: str
    resolved: bool
    keeper: Optional[FileInfo] = None
    removed: List[FileInfo] = field(default_factory=list)
    kept: List[FileInfo] = field(default_factory=list)
    reason: str = ""

    def space_freed(self) -> int:
        return sum(f.size for f in self.removed)


@dataclass
class RunReport:
    """Aggregated, privacy-friendly summary for a run (and for cron)."""
    scanned_files: int = 0
    scanned_bytes: int = 0
    hashed_files: int = 0
    groups_examined: int = 0
    actions: List[Action] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    stopped_by_cap: bool = False
    time_budget_hit: bool = False

    # --- tallies (computed from ``actions``) ---
    def resolved_count(self) -> int:
        return sum(1 for a in self.actions if a.kind != "DEDUP_SKIP")

    def skip_count(self) -> int:
        return sum(1 for a in self.actions if a.kind == "DEDUP_SKIP")

    def issues_identified(self) -> int:
        # resolved + ambiguity-skips together are the "issues" the cap counts.
        return len(self.actions)

    def planned_bytes(self) -> int:
        return sum(a.space_freed() for a in self.actions)
