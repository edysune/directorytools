"""SHA-256 integrity helpers.

By spec we only hash files that are "similar" (they already share a byte
size in a (name, size) duplicate group), so we never hash the whole tree —
only the candidates a rule engine actually wants to act on.
"""

from __future__ import annotations
import hashlib
import time
from typing import List, Optional, Sequence

from .models import FileInfo


class HashReadError(OSError):
    """A read ended early (EOF before the known file size was seen).

    The digest produced so far does NOT describe the file — treating it as
    valid would risk a false "equal" confirmation. Always treat as failure.
    """


def sha256_file(path: str, chunk_size: int = 1 << 20, expected_size: Optional[int] = None,
                retries: int = 1, retry_delay: float = 3.0) -> str:
    """Streaming SHA-256 of ``path`` (never holds a whole multi-GB file in RAM).

    If ``expected_size`` is given (from the directory entry), an EOF short of
    it means the share returned no more data (broken/hanging network mount) —
    the digest is untrustworthy and ``HashReadError`` is raised after a
    single retry, which also covers momentary SMB session blips.
    """
    last_err: Optional[BaseException] = None
    for attempt in range(retries + 1):
        h = hashlib.sha256()
        got = 0
        try:
            with open(path, "rb") as fh:
                while True:
                    b = fh.read(chunk_size)
                    if not b:
                        break
                    h.update(b)
                    got += len(b)
        except OSError as e:
            last_err = e
            if attempt < retries:
                time.sleep(retry_delay)
                continue
            raise
        if expected_size is None or got == expected_size:
            return h.hexdigest()
        last_err = HashReadError(f"early EOF after {got}/{expected_size} bytes")
        if attempt < retries:
            time.sleep(retry_delay)
            continue
        raise last_err
    raise last_err  # unreachable; keeps type-checkers honest


# SHA-256 of the EMPTY string. A non-empty file whose read() returns EOF
# (broken/hanging network share) would "hash" to this value — treating it as
# a real digest could confirm two DIFFERENT files as equal. Never trust it.
_EMPTY_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _broken(size: int, digest: str) -> bool:
    """True when a non-empty file came back as the empty-string digest."""
    return size > 0 and digest == _EMPTY_SHA


def confirm_with(hasher) -> "callable":
    """Build a ``(keeper, victims) -> confirmed victims`` closer over ONE hasher.

    ``hasher(path, size)`` must raise ``OSError`` on unreadable/early-EOF.
    Sharing ONE memoized hasher between the confirmation pass and the state
    pass is the point: without it, every candidate file is read twice off the
    network share (once here, once in state tracking).
    """

    def confirm(keeper: FileInfo, victims: Sequence[FileInfo]) -> List[FileInfo]:
        try:
            k_sha = hasher(keeper.path, keeper.size)
        except OSError:
            return []
        if _broken(keeper.size, k_sha):
            return []
        out: List[FileInfo] = []
        for v in victims:
            try:
                digest = hasher(v.path, v.size)
            except OSError:
                continue
            if _broken(v.size, digest):
                continue
            if digest == k_sha:
                out.append(v)
        return out

    return confirm


def confirm_equal(keeper: FileInfo, victims: Sequence[FileInfo]) -> List[FileInfo]:
    """Return the subset of ``victims`` whose SHA-256 equals ``keeper``'s.

    Only the keeper is hashed once; each victim is hashed lazily and compared.
    A victim whose file can no longer be opened is dropped (not a real dup).
    A non-empty file whose hash equals the EMPTY-string digest (EOF read on a
    broken share) is ALWAYS dropped — never treated as a matching digest.
    """
    try:
        keeper_sha = sha256_file(keeper.path, expected_size=keeper.size)
    except OSError:
        return []
    if _broken(keeper.size, keeper_sha):
        return []                     # keeper read was bogus: nothing confirmed
    out: List[FileInfo] = []
    for v in victims:
        try:
            digest = sha256_file(v.path, expected_size=v.size)
        except OSError:
            continue                  # unreadable or early-EOF: not confirmed
        if _broken(v.size, digest):
            continue                  # victim read was bogus: not confirmed
        if digest == keeper_sha:
            out.append(v)
    return out
