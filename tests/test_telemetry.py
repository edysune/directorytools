"""Live telemetry contract (the '1 hour, zero output' incident).

The weekly run on the CIFS box produced NO output for a full hour until an
outer timeout killed it.  Fixes pinned here:

1. every phase emits a timestamped stage line AS IT HAPPENS (scan progress,
   one line per hashed file with elapsed seconds + throughput);
2. each candidate file is read from storage EXACTLY ONCE per run — the
   dedup-confirm pass and the state-cache share ONE memoized hasher;
3. stage lines go through the Redactor: with encryption ON, no raw file
   name may appear in the log.
"""
from __future__ import annotations

import io

from cryptography.fernet import Fernet

from dedup_cleaner import cli, hashing
from dedup_cleaner.config import Config
from dedup_cleaner.logs import Redactor, StageLog


def _build(tmp):
    pref = tmp / "kept"; src = tmp / "src"
    pref.mkdir(parents=True); src.mkdir(parents=True)
    (pref / "v.mkv").write_bytes(b"same-bytes")
    (src / "v.mkv").write_bytes(b"same-bytes")
    (tmp / "solo.bin").write_bytes(b"lonely")
    return str(pref)


def _cfg(tmp, **kw):
    pref = _build(tmp)
    d = {"root": str(tmp), "preferred": [pref], "excluded": [],
         "dry_run": True, "allow_delete": False, "bad_file_types": [],
         "state_dir": str(tmp / "st"), "encrypt_file_name": False,
         "secret_key": "", "hash_check": True, "corruption_check": False}
    d.update(kw)
    return Config(**d)


def test_run_streams_stage_lines_with_per_file_hash_log(tmp_path):
    cfg = _cfg(tmp_path)
    buf = io.StringIO()
    report, st, perf = cli.run(cfg, StageLog(stream=buf))
    text = buf.getvalue()
    assert "[dedup_cleaner " in text                 # timestamped stage lines
    assert "run start:" in text
    assert "scan done:" in text
    assert "hash start:" in text and "hash done:" in text
    assert "fix stage:" in text                      # dry-run still announces it
    assert perf == []
    assert report.hashed_files == 2                  # only the 2 candidates


def test_each_candidate_read_from_storage_exactly_once(tmp_path, monkeypatch):
    """Confirm pass + state pass share the memo: 2 candidate files => 2 reads.

    Before the fix the confirm pass opened every file itself and the state
    loop re-read each candidate through the memoized hasher: 4 reads for 2
    files.  Counting real sha256_file calls pins the single-read contract.
    """
    cfg = _cfg(tmp_path)
    reads = []
    real = hashing.sha256_file

    def counting(path, chunk_size=1 << 20, expected_size=None, retries=1,
                 retry_delay=3.0):
        reads.append(path)
        return real(path, chunk_size, expected_size, retries, retry_delay)

    monkeypatch.setattr(hashing, "sha256_file", counting)
    buf = io.StringIO()
    report, st, perf = cli.run(cfg, StageLog(stream=buf))
    assert report.hashed_files == 2
    assert len(reads) == 2, f"candidate must be read once, got: {reads}"


def test_encrypted_run_never_logs_raw_names(tmp_path):
    cfg = _cfg(tmp_path, encrypt_file_name=True,
               secret_key=Fernet.generate_key().decode())
    buf = io.StringIO()
    report, st, perf = cli.run(cfg, StageLog(stream=buf))
    text = buf.getvalue()
    assert "v.mkv" not in text and "solo.bin" not in text
    assert "hash done:" in text                      # still telemetry-rich


def test_stage_log_disabled_writes_nothing():
    buf = io.StringIO()
    StageLog(stream=buf, enabled=False).stage("should not appear")
    assert buf.getvalue() == ""
