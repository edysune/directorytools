import os
from dedup_cleaner.config import Config
from dedup_cleaner.cli import run


def _build(tmp):
    pref = tmp / "kept"; src = tmp / "src"; ex = tmp / "EX"
    for d in (pref, src, ex):
        d.mkdir(parents=True, exist_ok=True)
    A = b"hello"; B = b"zzz"
    (pref / "v.mkv").write_bytes(A); (src / "v.mkv").write_bytes(A)
    (src / "n.txt").write_bytes(B);  (tmp / "n.txt").write_bytes(B)
    (src / "j.part").write_bytes(b"p"); (src / "e.mp4").write_bytes(b"")
    (ex / "v.mkv").write_bytes(A)
    return str(pref), str(src), str(ex)


def _cfg_with_paths(tmp, **kw):
    pref, src, ex = _build(tmp)
    d = {"root": str(tmp), "preferred": [pref], "excluded": [ex],
         "dry_run": True, "allow_delete": False, "bad_file_types": [".part"],
         "state_dir": str(tmp / "st"), "encrypt_file_name": False,
         "hash_check": False, "corruption_check": True}
    d.update(kw)
    return Config(**d)


def test_dry_run_reports_but_deletes_nothing(tmp_path):
    cfg = _cfg_with_paths(tmp_path)
    report, st, perf = run(cfg)
    assert report.scanned_files == 6
    assert len(report.actions) == 3
    assert perf == []                                # dry-run: nothing performed
    for a in report.actions:
        for v in a.removed:
            assert os.path.exists(v.path)
    assert any("0-byte" in w for w in report.warnings)


def test_master_switch_blocks_delete(tmp_path):
    cfg = _cfg_with_paths(tmp_path, dry_run=False, allow_delete=False)
    run(cfg)
    src = tmp_path / "src"
    assert (src / "v.mkv").exists()                   # guard held


def test_both_flags_delete(tmp_path):
    cfg = _cfg_with_paths(tmp_path, dry_run=False, allow_delete=True)
    run(cfg)
    assert not (tmp_path / "src" / "v.mkv").exists()
    assert (tmp_path / "kept" / "v.mkv").exists()     # preferred survives
    assert not (tmp_path / "src" / "j.part").exists() # bad type removed


def test_identical_dups_removed_when_hashed(tmp_path):
    # two byte-identical files, one preferred -> kept removed even w/ hash-check
    cfg = _cfg_with_paths(tmp_path, dry_run=False, allow_delete=True, hash_check=True)
    report, _, perf = run(cfg)
    assert any(a.kind == "DEDUP_KEEP" for a in report.actions)
    assert report.hashed_files >= 1


def test_hash_check_blocks_different_bytes_same_size(tmp_path):
    # same name, same size, DIFFERENT bytes -> NOT a real dup when hash-check on
    pref = tmp_path / "kept"; src = tmp_path / "src"
    (pref).mkdir(parents=True, exist_ok=True); (src).mkdir()
    (pref / "f.dat").write_bytes(b"ABCDEFGH")
    (src / "f.dat").write_bytes(b"87654321")          # same 8 bytes, diff content
    cfg = Config(root=str(tmp_path), preferred=[str(pref)], excluded=[],
                  dry_run=False, allow_delete=True, hash_check=True,
                  state_dir=str(tmp_path / "st"), encrypt_file_name=False,
                  bad_file_types=[], max_changes=10, corruption_check=False)
    report, _, _ = run(cfg)
    # without hash check it WOULD be deleted; with it, it is skipped
    keep = [a for a in report.actions if a.kind == "DEDUP_KEEP"]
    assert keep == [] or all(v.path != str(src / "f.dat") for a in keep for v in a.removed)
    assert (src / "f.dat").exists()                   # untouched
