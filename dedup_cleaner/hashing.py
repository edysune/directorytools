"""SHA-256 integrity helpers.

By spec we only hash files that are "similar" (they already share a byte
size in a (name, size) duplicate group), so we never hash the whole tree —
only the candidates a rule engine actually wants to act on.
"""

from __future__ import annotations
import hashlib
from typing import List, Optional, Sequence

from .models import FileInfo


def sha256_file(path: str, chunk_size: int = 1 << 20) -> str:
    """Streaming SHA-256 of ``path`` (never holds a whole TIB file in RAM)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def confirm_equal(keeper: FileInfo, victims: Sequence[FileInfo]) -> List[FileInfo]:
    """Return the subset of ``victims`` whose SHA-256 equals ``keeper``'s.

    Only the keeper is hashed once; each victim is hashed lazily and compared.
    A victim whose file can no longer be opened is dropped (not a real dup).
    """
    try:
        keeper_sha = sha256_file(keeper.path)
    except OSError:
        return []
    out: List[FileInfo] = []
    for v in victims:
        try:
            if sha256_file(v.path) == keeper_sha:
                out.append(v)
        except OSError:
            continue
    return out
