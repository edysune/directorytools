"""REGRESSION (box 5.1TB near-hang): with ``--hash-check`` on, only files that
are actual duplicate candidates (same name + size with >=1 other) may be
hashed for the state cache. Hashing the entire tree turned a weekly job into
a multi-terabyte I/O storm on CIFS.
"""
from dedup_cleaner.cli import main


def test_hash_state_scopes_to_duplicate_candidates_only(tmp_path, capsys):
    kept = tmp_path / "kept"; src = tmp_path / "src"; solo = tmp_path / "solo"
    kept.mkdir(); src.mkdir(); solo.mkdir()

    # real duplicate candidates: same name + size, DIFFERENT content
    (kept / "v.mp4").write_bytes(b"A" * 64)
    (src / "v.mp4").write_bytes(b"B" * 64)

    # non-candidates: unique (name, size) pairs -> must NEVER be hashed
    (solo / "unique1.bin").write_bytes(b"u" * 111)
    (solo / "unique2.bin").write_bytes(b"v" * 222)

    st = tmp_path / "st"
    rc = main(["--root", str(tmp_path), "--hash-check",
               "--state-dir", str(st),
               "--preferred", str(kept),
               "--bad-file-types", ".part"])
    assert rc == 0
    out = capsys.readouterr().out
    # exactly the two candidate files were hashed — the two unique ones were not
    assert "files hashed    : 2" in out

    csvs = list(st.rglob("*.csv"))
    assert csvs, "state CSV should have been written"
    text = csvs[0].read_text()
    rows = [line for line in text.splitlines() if line and not line.startswith("id,")]
    assert len(rows) == 2, f"state rows must be candidates only, got {rows}"
