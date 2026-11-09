import hashlib
import os
from dedup_cleaner import hashing
from dedup_cleaner.models import FileInfo


def F(path):
    return FileInfo(name=os.path.basename(path), path=path, size=os.path.getsize(path))


def test_sha256_matches_stdlib(tmp_path):
    f = tmp_path / "a"
    f.write_bytes(b"abc123")
    assert hashing.sha256_file(str(f)) == hashlib.sha256(b"abc123").hexdigest()


def test_confirm_equal_subset(tmp_path):
    a = str(tmp_path / "a"); b = str(tmp_path / "b"); c = str(tmp_path / "c")
    open(a, "wb").write(b"X"); open(b, "wb").write(b"X"); open(c, "wb").write(b"Y")
    keeper = F(a)
    out = hashing.confirm_equal(keeper, [F(b), F(c)])
    assert {o.path for o in out} == {b}


def test_empty_string_digest_never_confirms_nonempty(tmp_path, monkeypatch):
    """REGRESSION (box CIFS EOF): a share that returns 0 bytes for a
    non-empty file yields the EMPTY-SHA digest; if the same happens for two
    different files, a naive equality check would 'confirm' them and delete
    the wrong victim. Both keeper-side and victim-side must be rejected."""
    a = str(tmp_path / "a"); b = str(tmp_path / "b"); c = str(tmp_path / "c")
    open(a, "wb").write(b"REAL-KEEPER"); open(b, "wb").write(b"OTHER-1")
    open(c, "wb").write(b"OTHER-2")

    empty = hashing._EMPTY_SHA
    def fake(path: str) -> str:
        return empty  # broken share: every read() returns EOF

    monkeypatch.setattr(hashing, "sha256_file", fake)
    assert hashing.confirm_equal(F(a), [F(b), F(c)]) == []          # keeper bogus
    monkeypatch.undo()

    # keeper reads fine, but a victim's read is bogus -> that victim is dropped
    import hashlib as _h
    real_a = _h.sha256(b"REAL-KEEPER").hexdigest()
    def fake2(path: str) -> str:
        return real_a if path == a else empty
    monkeypatch.setattr(hashing, "sha256_file", fake2)
    assert hashing.confirm_equal(F(a), [F(b), F(c)]) == []          # victims bogus


def test_two_genuinely_empty_files_still_confirm(tmp_path):
    """0-byte files genuinely hash to the empty digest — that pair is a valid
    (nameless-content) duplicate and must still be confirmable."""
    a = str(tmp_path / "a"); b = str(tmp_path / "b")
    open(a, "wb").close(); open(b, "wb").close()
    out = hashing.confirm_equal(F(a), [F(b)])
    assert {o.path for o in out} == {b}
