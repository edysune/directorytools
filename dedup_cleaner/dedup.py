"""Pure dedup rule engine.

The three preference cases the tool must honour (spec, verbatim intent):

* **one preferred + one-or-more non-preferred**  -> keep the preferred member,
  delete the non-preferred duplicate(s).  (preferred never deleted)
* **all members under preferred paths**          -> SKIP (all equal weight)
* **no member under a preferred path**           -> SKIP (never delete on
  ambiguity)

A group is "consumed" as soon as it produces a decision, so a (name, size)
pair is never re-evaluated within the same run, and the ``max_changes`` cap
counts both resolved actions and ambiguity-skips.
"""

from __future__ import annotations
import os
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from . import paths
from .models import Action, FileInfo


def is_bad_type(name: str, bad_types: Iterable[str]) -> bool:
    """True if ``name`` ends in one of ``bad_types`` (case-insensitive)."""
    if not bad_types:
        return False
    ext = os.path.splitext(name)[1].lower()
    return ext in {t.lower() for t in bad_types if t}


def find_bad_type_files(files: Sequence[FileInfo],
                        bad_types: Iterable[str]) -> List[Action]:
    """Bad extensions are removed regardless of preference (dry-run gated)."""
    if not bad_types:
        return []
    out: List[Action] = []
    for f in files:
        if is_bad_type(f.name, bad_types):
            out.append(Action(
                kind="REMOVE_BAD_TYPE", resolved=True, keeper=None,
                removed=[f],
                reason="bad file type " + os.path.splitext(f.name)[1],
            ))
    return out


def resolve_group(members: Sequence[FileInfo],
                  preferred: Iterable[str]) -> Tuple[bool, Action]:
    """Prefer-then-keep decision for one (name, size) group (len>=2), pure."""
    pref = [m for m in members if paths.is_preferred(m.path, preferred)]
    nonpref = [m for m in members if not paths.is_preferred(m.path, preferred)]
    if pref and nonpref:
        return True, Action(
            kind="DEDUP_KEEP", resolved=True, keeper=pref[0], removed=nonpref,
            reason="preferred path wins; non-preferred duplicate(s) removed",
        )
    if pref:
        return False, Action(
            kind="DEDUP_SKIP", resolved=False, kept=pref,  # type: ignore[arg-type]
            reason="all members under preferred paths; equal weight, not deletable",
        )
    return False, Action(
        kind="DEDUP_SKIP", resolved=False, kept=members,  # type: ignore[arg-type]
        reason="no member under a preferred path; ambiguity not resolved",
    )


def plan_dedup(by_name_size: Dict[Tuple[str, int], List[FileInfo]],
               preferred: Iterable[str],
               cap: int,
               consumed: Optional[Set[Tuple[str, int]]] = None,
               confirm=None) -> "tuple[list, bool]":
    """Produce dedup actions for all (name, size) groups, honouring the cap.

    ``confirm`` is an optional callable ``(keeper, victims) -> confirmed_victims``
    used when hash-checking is on; a victim only survives if it passes.
    Returns ``(actions, stopped_by_cap)``.
    """
    actions: List[Action] = []
    consumed = consumed if consumed is not None else set()
    stopped = False
    for (name, size), members in sorted(by_name_size.items()):
        if len(members) < 2:
            continue
        if (name, size) in consumed:
            continue
        if len(actions) >= cap:
            stopped = True
            break
        resolved, action = resolve_group(members, preferred)
        if resolved and action.removed and confirm is not None:
            confirmed = confirm(action.keeper, action.removed)
            if not confirmed:
                action = Action(kind="DEDUP_SKIP", resolved=False,
                               reason="hash mismatch: not byte-identical to keeper")
            else:
                action.removed = confirmed
        consumed.add((name, size))
        actions.append(action)
    return actions, stopped
