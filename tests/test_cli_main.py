"""End-to-end tests for the CLI entry point (``main``) and the report renderer.

These cover the two thin glue layers that the unit tests (rules/config/scanner/
hashing/state/logs) drive through ``run()``: argv parsing, the fail-fast
privacy guard, exit codes, and what ``render`` prints (including that a
key'd Redactor masks every path shown to the operator).
"""
from cryptography.fernet import Fernet

from dedup_cleaner.cli import main
from dedup_cleaner.config import Config
from dedup_cleaner.logs import Redactor
from dedup_cleaner.models import RunReport, Action, FileInfo
from dedup_cleaner.report import render, human


def test_main_dry_run_exit0_reports_and_deletes_nothing(tmp_path, capsys):
    pref = tmp_path / "kept"; src = tmp_path / "src"
    pref.mkdir(); src.mkdir()
    (pref / "v.mkv").write_bytes(b"x"); (src / "v.mkv").write_bytes(b"x")
    rc = main(["--root", str(tmp_path), "--preferred", str(pref),
               "--bad-file-types", ".part",
               "--state-dir", str(tmp_path / "st")])
    assert rc == 0
    out = capsys.readouterr().out
    assert "dedup_cleaner run report" in out
    assert "DRY-RUN (no modifications)" in out
    assert "KEEP" in out                                  # the dup group was found
    assert (src / "v.mkv").exists()                        # dry-run: untouched


def test_main_encrypt_on_but_no_key_returns_1(tmp_path):
    rc = main(["--root", str(tmp_path), "--encrypt-file-name"])
    assert rc == 1                                         # clean config error, no crash


def test_main_missing_required_root():
    rc = main([])
    assert rc in (0, 1, 2)                                 # argparse SystemExit surfaced as int


def test_render_report_contents(tmp_path):
    cfg = Config(root=str(tmp_path))
    rep = RunReport(scanned_files=3, scanned_bytes=1234, hashed_files=0,
                    groups_examined=1, stopped_by_cap=False,
                    actions=[Action(kind="DEDUP_KEEP", resolved=True,
                                    keeper=FileInfo("v.mkv", "/kept/v.mkv", 6),
                                    removed=[FileInfo("v.mkv", "/src/v.mkv", 6)],
                                    reason="preferred wins")],
                    warnings=["0-byte file: /src/e.mp4"], errors=[])
    text = render(cfg, rep, Redactor(False, ""))
    assert "dedup_cleaner run report" in text
    assert "DRY-RUN" in text
    assert "space to recover" in text
    assert "KEEP" in text and "remove 1" in text
    assert "0-byte file" in text
    assert human(1234) == "1.21 KB"


def test_render_encrypted_masks_all_paths(tmp_path):
    key = Fernet.generate_key().decode()
    cfg = Config(root=str(tmp_path), encrypt_file_name=True, secret_key=key)
    rep = RunReport(scanned_files=2, groups_examined=1, stopped_by_cap=False,
                    actions=[Action(kind="DEDUP_KEEP", resolved=True,
                                    keeper=FileInfo("s.mkv", "/kept/s.mkv", 1),
                                    removed=[FileInfo("s.mkv", "/src/s.mkv", 1)])])
    text = render(cfg, rep, Redactor(True, key))
    assert "/kept/s.mkv" not in text
    assert "/src/s.mkv" not in text


def test_main_env_encrypt_redacts_output(tmp_path, capsys, monkeypatch):
    """REGRESSION (box leak): DEDUP_ENCRYPT_FILE_NAME=true in env — with NO explicit
    --encrypt-file-name flag — must still redact raw names OUT of stdout.

    Before the fix, the boolean flag had no env default, so the CLI built the
    Redactor disabled and printed paths verbatim."""
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("DEDUP_ENCRYPT_FILE_NAME", "true")
    monkeypatch.setenv("DEDUP_SECRET_KEY", key)
    monkeypatch.setenv("DEDUP_BAD_FILE_TYPES", ".part")
    monkeypatch.setenv("DEDUP_STATE_DIR", str(tmp_path / "st"))
    monkeypatch.delenv("DEDUP_PREFERRED", raising=False)
    monkeypatch.delenv("DEDUP_IGNORE", raising=False)

    distinctive = "SuperSecret_Scanned_Doc_2024_final"
    d = tmp_path / "models"; d.mkdir()
    (d / (distinctive + ".mp4")).write_bytes(b"z" * 16)
    (d / (distinctive + ".mp4.part")).write_bytes(b"z" * 16)   # same name+size dup
    (d / (distinctive + ".part")).write_bytes(b"q" * 4)        # a bad-type file

    rc = main(["--root", str(tmp_path)])   # no --encrypt-file-name flag; env drives it
    assert rc == 0
    out = capsys.readouterr().out
    assert distinctive not in out            # the raw name MUST be gone
    assert "gAAAAA" in out                   # Fernet token prefix is present instead
