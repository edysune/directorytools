"""Path normalization + the two path predicates the rules depend on.

Both ``is_excluded`` and ``is_preferred`` treat a configured root as covering
that directory and every recursive child beneath it. Matching is on full path
components so ``/data/a`` is NOT "inside" ``/data/a2`` (no string substring
false positives).
"""

from __future__ import annotations
from typing import Iterable, List, Optional
import os
import posixpath


def normalize(p: str) -> str:
    """Absolute, POSIX, deduplicated form of ``p`` (works on any OS host)."""
    p = os.path.abspath(os.path.normpath(str(p)))
    # on POSIX abspath already gives /-separated paths.
    return p.replace(os.sep, "/")


def parse_list(raw: str) -> List[str]:
    """Split a space- or comma-separated env value into a list of paths."""
    if not raw:
        return []
    items = raw.replace(",", " ").split()
    out = []
    for it in items:
        it = it.strip().rstrip("/")
        if it:
            out.append(it)
    return out


def is_excluded(path: str, excluded: Iterable[str]) -> bool:
    """True if ``path`` is under (or equals) any excluded root (inclusive)."""
    np = normalize(path)
    if not excluded:
        return False
    for root in excluded:
        nr = normalize(root).rstrip("/")
        if np == nr or np.startswith(nr + "/"):
            return True
    return False


def is_preferred(path: str, preferred: Iterable[str]) -> bool:
    """True if ``path`` is under (or equals) any preferred root (inclusive)."""
    return preferred_rank(path, preferred) is not None


def preferred_rank(path: str, preferred: Iterable[str]) -> Optional[int]:
    """Rank of ``path`` in an *ordered* preferred list.

    Returns the index of the FIRST list entry the path falls under (or equals),
    so lower index == stronger preference. ``None`` if the path is not under
    any preferred root (i.e. non-preferred, and ranked below every entry).
    """
    np = normalize(path)
    if not preferred:
        return None
    for i, root in enumerate(preferred):
        nr = normalize(root).rstrip("/")
        if np == nr or np.startswith(nr + "/"):
            return i
    return None
