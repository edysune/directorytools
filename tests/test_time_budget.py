"""Wall-clock budget: the run must self-terminate cleanly on expiry.

Contract (from user requirements on the CIFS box):
- On expiry the process saves state, emits a partial report, and exits.
- The fix stage (deletions) NEVER runs after a budget hit — it is always last.
- No limit configured (0) => no alarm at all, normal behaviour.
"""
from __future__ import annotations

import time

from dedup_cleaner import cli, hashing, scanner
from dedup_cleaner.config import from_env
from dedup_cleaner.logs import Redactor, StageLog
from dedup_cleaner.models import RunReport


def test_hasher_threads_size_into_sha256_file(tmp_path, monkeypatch):
    """_hasher_for passes the known size through, so sha256_file can detect
    early-EOF reads; memo still avoids a second read of the same path."""
    calls = []

    def fake(path, chunk_size=1 << 20, expected_size=None, retries=1, retry_delay=3.0):
        calls.append((path, expected_size))
        return "ab" * 32

    monkeypatch.setattr(hashing, "sha256_file", fake)
    rep = RunReport()
    h = cli._hasher_for(rep, Redactor(False, ""), StageLog(enabled=False))
    p = str(tmp_path / "a.bin")
    assert h(p, 111) == "ab" * 32
    assert h(p, 111) == "ab" * 32          # memo hit
    assert rep.hashed_files == 1            # real I/O happened once
    assert calls == [(p, 111)]              # size propagated every call
    assert h(p) == "ab" * 32                # size-optional still works


def test_budget_hit_exits_3_and_deletes_nothing(tmp_path, monkeypatch):
    root = tmp_path / "data"
    keep = root / "keep"
    keep.mkdir(parents=True)
    (root / "dup.txt").write_bytes(b"x" * 4096)
    (keep / "dup.txt").write_bytes(b"x" * 4096)

    # slow the scan down past the 1s budget (capture the real fn BEFORE
    # replacing: the replacement must delegate to the original, not itself)
    real_iter = scanner.iter_files
    def slow_iter(rootdir, excluded):
        time.sleep(3.0)
        return real_iter(rootdir, excluded)
    monkeypatch.setattr(scanner, "iter_files", slow_iter)

    # verify the alarm is installed+cleared AND let the REAL alarm fire, so
    # the 1s budget genuinely triggers (wrap, don't replace-with-noop)
    inst, clr = [], []
    real_install, real_clear = cli._install_budget, cli._clear_alarm
    monkeypatch.setattr(cli, "_install_budget",
                        lambda s: (inst.append(s), real_install(s)))
    monkeypatch.setattr(cli, "_clear_alarm", lambda: clr.append(1) or real_clear())

    # dry_run off + allow_delete on: if the budget logic regressed and the run
    # somehow finished, the fix stage WOULD delete a victim — assert it didn't
    rc = cli.main(["--root", str(root), "--time-budget-s", "1",
                   "--dry-off", "--allow-delete"])

    assert rc == 3                      # budget exit code, not 0/1/2
    assert inst == [1] and clr == [1]   # alarm installed and cleared exactly once
    assert (root / "dup.txt").exists()  # NOTHING deleted
    assert (keep / "dup.txt").exists()

    import signal
    signal.signal(signal.SIGALRM, signal.default_int_handler)  # restore


def test_budget_zero_never_installs_alarm(tmp_path, monkeypatch):
    root = tmp_path / "d"; root.mkdir()
    (root / "one.txt").write_bytes(b"abc")
    inst, clr = [], []
    monkeypatch.setattr(cli, "_install_budget", lambda s: inst.append(s))
    monkeypatch.setattr(cli, "_clear_alarm", lambda: clr.append(1))
    rc = cli.main(["--root", str(root), "--time-budget-s", "0"])
    assert rc == 0
    assert inst == [] and clr == []     # budget=0 -> no alarm at all


def test_config_wiring(monkeypatch):
    monkeypatch.setenv("DEDUP_TIME_BUDGET_S", "42")
    monkeypatch.setenv("DEDUP_ROOT", "/tmp/never-scan")
    try:
        cfg = from_env()
        assert cfg.time_budget_s == 42
        cfg2 = cli.from_args(["--root", "/tmp/never-scan"])
        assert cfg2.time_budget_s == 42             # env default respected
        cfg3 = cli.from_args(["--root", "/tmp/never-scan", "--time-budget-s", "7"])
        assert cfg3.time_budget_s == 7              # flag overrides env
    finally:
        monkeypatch.delenv("DEDUP_ROOT")
