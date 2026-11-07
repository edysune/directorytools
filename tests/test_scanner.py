import os
from dedup_cleaner import scanner


def test_scan_excludes_and_indexes(tmp_path):
    (tmp_path / "kept").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "EX").mkdir()
    (tmp_path / "kept" / "v.mkv").write_bytes(b"x")
    (tmp_path / "src" / "v.mkv").write_bytes(b"x")
    (tmp_path / "EX" / "v.mkv").write_bytes(b"x")

    files = list(scanner.iter_files(str(tmp_path), [str(tmp_path / "EX")]))
    assert len(files) == 2                      # EX subtree never scanned
    by_ns, by_sz, total = scanner.build_indexes(files)
    assert ("v.mkv", 1) in by_ns and len(by_ns[("v.mkv", 1)]) == 2
    assert by_sz[1] and total == 2
