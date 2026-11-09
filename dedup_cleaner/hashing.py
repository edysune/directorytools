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


# SHA-256 of the EMPTY string. A non-empty file whose read() returns EOF
# (broken/hanging network share) would "hash" to this value — treating it as
# a real digest could confirm two DIFFERENT files as equal. Never trust it.
_EMPTY_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _broken(size: int, digest: str) -> bool:
    """True when a non-empty file came back as the empty-string digest."""
    return size > 0 and digest == _EMPTY_SHA


def confirm_equal(keeper: FileInfo, victims: Sequence[FileInfo]) -> List[FileInfo]:
    """Return the subset of ``victims`` whose SHA-256 equals ``keeper``'s.

    Only the keeper is hashed once; each victim is hashed lazily and compared.
    A victim whose file can no longer be opened is dropped (not a real dup).
    A non-empty file whose hash equals the EMPTY-string digest (EOF read on a
    broken share) is ALWAYS dropped — never treated as a matching digest.
    """
    try:
        keeper_sha = sha256_file(keeper.path)
    except OSError:
        return []
    if _broken(keeper.size, keeper_sha):
        return []                     # keeper read was bogus: nothing confirmed
    out: List[FileInfo] = []
    for v in victims:
        try:
            digest = sha256_file(v.path)
        except OSError:
            continue
        if _broken(v.size, digest):
            continue                  # victim read was bogus: not confirmed
        if digest == keeper_sha:
            out.append(v)
    return out
