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
