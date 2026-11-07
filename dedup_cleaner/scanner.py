"""Recursive walk of ``root`` that never descends into excluded directories.

``os.scandir``-based (faster than ``os.walk`` on deep trees) and prunes each
directory in place the moment it matches an exclusion, so excluded subtrees
are never even entered. File metadata is collected with ``lstat`` (no follow
of symlinks) and only ``name`` + size are kept for identity — the rest stays
out of the hot path.
"""

from __future__ import annotations
import os
from typing import Iterable, Iterator, List, Tuple

from . import paths
from .models import FileInfo


def iter_files(root: str, excluded: Iterable[str] = (),
               ) -> Iterator[FileInfo]:
    """Yield every regular file under ``root`` that is not under an exclusion.

    Directory-pruning is done on the way down so the traversal is O(visible
    files) regardless of the total tree size behind the excluded subtrees.
    """
    excluded = [paths.normalize(p) for p in excluded if p]
    stack: List[str] = [paths.normalize(root)]
    while stack:
        d = stack.pop()
        if any((e := paths.normalize(p)) and (d == e or d.startswith(e.rstrip('/') + "/")) for p in excluded if p):
            continue
        try:
            with os.scandir(d) as it:
                entries = list(it)
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                elif e.is_file(follow_symlinks=False):
                    st = e.stat(follow_symlinks=False)
                    yield FileInfo(name=e.name, path=e.path, size=st.st_size,
                                   mtime=int(st.st_mtime))
            except OSError:
                continue


def build_indexes(files: Iterable[FileInfo]) -> "tuple[dict, dict, int]":
    """Return (by_name_size, by_size, total_bytes)."""
    from collections import defaultdict
    by_ns = defaultdict(list)
    by_sz = defaultdict(list)
    total = 0
    for f in files:
        by_ns[f.key()].append(f)
        by_sz[f.size].append(f)
        total += f.size
    return dict(by_ns), dict(by_sz), total
