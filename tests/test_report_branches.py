"""Branch coverage for the report renderer and a couple of run() edges."""
from dedup_cleaner.config import Config
from dedup_cleaner.cli import run
from dedup_cleaner.logs import Redactor
from dedup_cleaner.models import RunReport, Action, FileInfo
from dedup_cleaner.report import render, human
from dedup_cleaner.state import State


def rep(actions=(), warnings=(), errors=(), cap=False, deleted=False):
    return RunReport(scanned_files=1, scanned_bytes=1, hashed_files=0,
                     groups_examined=1, stopped_by_cap=cap,
                     actions=list(actions), warnings=list(warnings),
                     errors=list(errors))


def cfg(root, dry_run=True, allow_delete=False):
    return Config(root=root, dry_run=dry_run, allow_delete=allow_delete)


def test_render_skip_and_bad_type(tmp_path):
    r = rep(actions=[
        Action(kind="DEDUP_SKIP", resolved=False,
               keeper=FileInfo("a", "/x/a", 1),
               reason="no preferred path wins",
               kept=[FileInfo("a", "/x/a", 1), FileInfo("a", "/y/a", 1)]),
        Action(kind="REMOVE_BAD_TYPE", resolved=True,
               removed=[FileInfo("z.part", "/x/z.part", 4)],
               reason="bad file type .part"),
    ])
    text = render(cfg(str(tmp_path)), r, Redactor(False, ""))
    assert "SKIP" in text and "no preferred path wins" in text
    assert "BAD" in text and ".part" in text


def test_render_deletion_enabled_and_guard_modes(tmp_path):
    on  = render(cfg(str(tmp_path), dry_run=False, allow_delete=True),
                 rep(), Redactor(False, ""))
    guard = render(cfg(str(tmp_path), dry_run=False, allow_delete=False),
                   rep(), Redactor(False, ""))
    assert "DELETION ENABLED" in on
    assert "allow-delete OFF" in guard


def test_render_cap_state_performed_errors(tmp_path):
    r = rep(cap=True, warnings=["w1"], errors=["e1"])
    rd = Redactor(False, "")
    st = State(rd); st.add_or_update(FileInfo("a", "/x/a", 1), "")
    text = render(cfg(str(tmp_path)), r, rd, performed=["deleted /x/z.part"], state=st)
    assert "stopped early (hit max_changes" in text
    assert "state rows" in text and "deleted /x/z.part" in text
    assert "warnings" in text and "e1" in text


def test_human_units():
    assert human(0) == "0 B"
    assert human(1023) == "1023 B"
    assert human(1024) == "1.00 KB"
    assert human(5 * 1024 * 1024) == "5.00 MB"
    assert human(2 * 1024 ** 3) == "2.00 GB"
    assert human(1024 ** 4) == "1.00 TB"


def test_run_missing_root_reports_clean_error(tmp_path, monkeypatch):
    c = cfg(str(tmp_path / "does-not-exist"))
    report, st, performed = run(c)
    assert report.scanned_files == 0
    assert any("root directory not found" in e for e in report.errors)
    assert st is None and performed == []
