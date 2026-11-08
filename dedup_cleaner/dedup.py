"""Pure dedup rule engine.

Preference semantics (spec + ranked tie-breaker):

* The ``DEDUP_PREFERRED`` list is ORDERED: earlier entries outrank later ones.
  A file is assigned the rank of the first list root it falls under (lower is
  stronger); not under any root == non-preferred (rank below every entry).
* **no member preferred**                       -> SKIP (never delete on
  ambiguity)
* **multiple members preferred:**
  - exactly one holds the TOP rank              -> that member is the keeper;
    every other member (lower-ranked preferred AND non-preferred) is the
    removal candidate.  A copy in a weaker preferred dir loses to the copy in
    the stronger one (e.g. Models keeps over Categories).
  - two-or-more members share the TOP rank      -> SKIP (tied at equal
    weight; still counted toward the cap).
* Invariant: a file is never removed in favour of an equal- or lower-ranked
  one, and a non-preferred file always loses to any preferred file.

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
    """Ranked keep/drop decision for one (name, size) group (len>=2), pure.

    The preferred list is an ORDER of strength (see module docstring). Top
    rank wins if unique; a top-rank tie is a SKIP.
    """
    ranked = [(paths.preferred_rank(m.path, preferred), m) for m in members]
    pref = [(rk, m) for rk, m in ranked if rk is not None]
    if not pref:
        return False, Action(
            kind="DEDUP_SKIP", resolved=False, kept=list(members),  # type: ignore[arg-type]
            reason="no member under a preferred path; ambiguity not resolved",
        )
    best = min(rk for rk, _ in pref)
    best_members = [m for rk, m in ranked if rk == best]
    if len(best_members) > 1:
        return False, Action(
            kind="DEDUP_SKIP", resolved=False, kept=list(members),  # type: ignore[arg-type]
            reason="multiple members share the top-preferred rank; tied, not deletable",
        )
    keeper = best_members[0]
    removed = [m for m in members if m.path != keeper.path]
    return True, Action(
        kind="DEDUP_KEEP", resolved=True, keeper=keeper, removed=removed,
        reason="top-ranked preferred path keeps; lower-ranked/non-preferred duplicate(s) removed",
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
