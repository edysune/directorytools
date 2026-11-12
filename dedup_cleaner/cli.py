"""Orchestrator: config -> scan -> dedup -> fix -> report.

Kept dependency-free (stdlib + ``cryptography``) so the container is small.

Every phase emits a live, redacted stage line (with elapsed seconds) so a
slow or wedged run is SELF-DOCUMENTING: the log itself shows which phase ate
the wall-clock time instead of going silent until process exit.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from typing import List, Optional

from . import scanner, dedup as dedup_rules, hashing
from .config import Config, from_args, from_env, _load_env_file
from .fixer import apply as apply_deletions
from .logs import Redactor, ConfigKeyError, StageLog
from .media import is_media, probe_media
from .models import RunReport
from .report import render
from .state import State

# how often the scan loop prints a progress line (files enumerated)
LOG_EVERY = 1000


def _human(n: int) -> str:
    """Bytes -> short human string for stage lines."""
    x = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if x < 1024 or unit == "TB":
            return f"{x:.2f} {unit}"
        x /= 1024
    return f"{x:.2f} TB"


class _BudgetExceeded(Exception):
    """Raised from the SIGALRM handler when the run exceeds its wall-clock budget."""


def _install_budget(seconds: int) -> None:
    def handler(signum, frame):
        raise _BudgetExceeded()
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)


def _clear_alarm() -> None:
    signal.alarm(0)


def _hasher_for(report: RunReport, redactor: Redactor, log: StageLog):
    """Return a hasher that reads each file at most ONCE per run.

    The SAME hasher instance backs both the dedup confirmation pass and the
    state cache loop; with the memo a file requested by both passes is read
    from (possibly network) storage exactly once. ``report.hashed_files``
    counts real I/O, so it increments once. ``size`` — when known — makes
    the read size-validated (early-EOF = error). Every real read logs a
    START line before reading and a DONE line (bytes/seconds) after, so the
    log streams continuously while hashing runs.
    """
    memo: dict = {}

    def hasher(path: str, size: Optional[int] = None) -> str:
        if path in memo:
            return memo[path]
        shown = redactor.display(path)
        log.stage(f"hash start: {shown} ({_human(size) if size is not None else 'size unknown'})")
        t = time.monotonic()
        digest = hashing.sha256_file(path, expected_size=size)
        secs = max(time.monotonic() - t, 1e-9)
        rate = f"{(size or 0) / secs / 1e6:.0f} MB/s" if size else "-"
        report.hashed_files += 1
        log.stage(f"hash done:   {shown} in {secs:.1f}s ({rate})")
        memo[path] = digest
        return digest
    return hasher


def run(cfg: Config, log: Optional[StageLog] = None) -> "tuple[RunReport, State|None, List[str]]":
    """Execute one scan + clean pass.  Returns ``(report, state, performed)``."""
    report = RunReport()
    log = log if log is not None else StageLog()

    # privacy fail-fast: constructing the Redactor raises ConfigKeyError if
    # enabled without a valid key -- we catch it here and surface it cleanly.
    redactor = Redactor(cfg.encrypt_file_name, cfg.secret_key)

    root = cfg.root
    if not os.path.isdir(root):
        report.errors.append(f"root directory not found: {redactor.display(root)}")
        return report, None, []

    log.stage("run start: "
              f"dry_run={cfg.dry_run} allow_delete={cfg.allow_delete} "
              f"delete_bad_only={cfg.delete_bad_only} hash_check={cfg.hash_check} "
              f"budget={cfg.time_budget_s}s max_changes={cfg.max_changes}")

    st = None
    try:
        # 1) scan ---------------------------------------------------------------
        log.stage(f"scan: walking tree ({len(cfg.excluded)} excluded roots pruned)")
        files: List = []
        for i, f in enumerate(scanner.iter_files(root, cfg.excluded), 1):
            files.append(f)
            if i % LOG_EVERY == 0:
                log.stage(f"scan progress: {i} files enumerated")
        by_ns, by_sz, total_bytes = scanner.build_indexes(files)
        report.scanned_files = len(files)
        report.scanned_bytes = total_bytes
        report.groups_examined = sum(1 for m in by_ns.values() if len(m) >= 2)
        log.stage(f"scan done: {report.scanned_files} files / {_human(total_bytes)}; "
                  f"{report.groups_examined} dup groups in {log.elapsed:.1f}s")

        # 2) state (additive; loaded BEFORE decisions so unchanged files are cheap)
        use_state = cfg.corruption_check or cfg.hash_check
        st = None
        hasher = None
        confirm = None
        if use_state:
            st = State.load(cfg.state_csv, redactor)
            log.stage(f"state: loaded {len(st.rows)} tracked rows")
            if cfg.hash_check or cfg.corruption_check:
                if not st.verify_decryption():
                    # spec: on decrypt failure, skip SHA-hash validation for this run
                    cfg.hash_check = False
                    log.stage("state: decryption FAILED — hash validation disabled this run")
            if cfg.hash_check:
                # ONE memoized hasher for BOTH passes (confirm + state):
                # a candidate file is read off the share exactly once per run.
                hasher = _hasher_for(report, redactor, log)
                confirm = hashing.confirm_with(hasher)
                log.stage("hash mode ON: candidates will be hashed once, shared by both passes")

        # 4) dedup group decisions (respect cap; ambiguity counts)
        actions, stopped_by_cap = dedup_rules.plan_dedup(
            by_ns, cfg.preferred, cfg.max_changes, confirm=confirm)
        report.actions.extend(actions)
        report.stopped_by_cap = stopped_by_cap
        log.stage(f"dedup plan: {len(actions)} actions "
                  f"({report.resolved_count()} resolved / {report.skip_count()} skipped)"
                  + (" [CAP HIT]" if stopped_by_cap else ""))

        # 5) bad file types (no cap -- cheap, unambiguous "delete .part" style)
        bad_actions = dedup_rules.find_bad_type_files(files, cfg.bad_file_types)
        report.actions.extend(bad_actions)
        log.stage(f"bad-type pass: {len(bad_actions)} files")

        # 6) corruption findings (additive): 0-byte + optional media probe
        if cfg.corruption_check:
            for f in files:
                if f.size == 0:
                    report.warnings.append(
                        f"0-byte file: {redactor.display(f.path)}")
            for f in files:
                if is_media(f.name):
                    try:
                        result = probe_media(f.path)
                    except Exception as exc:
                        result = (False, f"probe error: {exc}")
                    if result is not None:
                        ok, msg = result
                        if not ok:
                            report.warnings.append(
                                f"media probe flagged: {redactor.display(f.path)}: {msg}")

        # 7) state: persist (new/changed) + prune stale dirs + save
        if use_state and st is not None:
            if cfg.hash_check and hasher is not None:
                # Hash cost is bounded to files that are ACTUAL duplicate
                # candidates (same name+size as >=1 other). Hashing the whole
                # tree would be multi-TB of pointless I/O on the weekly run —
                # the state cache only matters for files we might dedup.
                candidate_ids = {
                    id(f)
                    for members in by_ns.values()
                    if len(members) >= 2
                    for f in members
                }
                tracked = 0
                for f in files:
                    if id(f) in candidate_ids and st.should_track_size(f):
                        st.process(f, lambda _p, _f=f: hasher(_p, _f.size))
                        tracked += 1
                log.stage(f"state track: {tracked} candidate files needed new/updated rows")
            else:
                for f in files:
                    st.process(f, hasher)  # size-only tracking (no hash cost)
            known_dirids = {_digest_dirinfo(f.path) for f in files}
            pruned = st.prune_stale(known_dirids)
            try:
                st.save(cfg.state_csv)
                log.stage(f"state saved ({len(st.rows)} rows, {pruned} stale pruned)")
            except OSError as exc:
                report.warnings.append(f"state save failed: {exc}")
    except _BudgetExceeded:
        # Wall-clock budget hit: stop NOW with what we have. Persist the
        # state cache if one was built, and never run the fix stage — the
        # fix stage is always last, so at this point NOTHING has been deleted.
        report.time_budget_hit = True
        report.warnings.append(
            f"time budget ({cfg.time_budget_s}s) exceeded — partial run; "
            f"state saved where possible; NO deletions performed")
        log.stage("TIME BUDGET EXCEEDED — stopping early; NO deletions performed")
        if st is not None:
            try:
                st.save(cfg.state_csv)
            except OSError:
                pass
        return report, st, []

    # 8) fix stage (gated by dry_run off AND allow_delete on)
    planned = sum(len(a.removed) for a in report.actions)
    log.stage(f"fix stage: {planned} removals "
              f"{'SKIPPED (dry-run)' if not cfg.deletion_enabled() else 'APPROVED for deletion'}")
    performed = apply_deletions(cfg, report, redactor)
    log.stage(f"fix stage done: {len(performed)} files actually deleted")
    return report, st, performed


def _digest_dirinfo(path: str) -> str:
    """sha256 of the containing directory; matches State's ``dirid`` space."""
    from .state import _digest
    return _digest(os.path.dirname(path))


def main(argv=None) -> int:
    """Entry point.  Returns a process exit code (0 clean, 1 config, 2 error, 3 budget)."""
    try:
        cfg = from_args(argv)
    except SystemExit as e:  # argparse error
        return int(e.code) if isinstance(e.code, int) else 2

    # optional .env overlay (docker-compose usually passes these directly)
    env_file = os.environ.get("DEDUP_ENV_FILE", "/run/secrets/dedup_cleaner.env")
    if os.path.isfile(env_file):
        _load_env_file(env_file)

    # privacy: fail FAST before scanning if encrypt_file_name on but no key.
    try:
        redactor = Redactor(cfg.encrypt_file_name, cfg.secret_key)
    except ConfigKeyError as exc:
        sys.stderr.write(f"[dedup_cleaner] config error: {exc}\n")
        return 1

    log = StageLog()
    log.stage("container alive; beginning run")

    # wall-clock backstop (in-container, so the container can never outlive
    # a hung CIFS read by orphaning — the outer `timeout` is a second layer)
    if cfg.time_budget_s and cfg.time_budget_s > 0:
        _install_budget(cfg.time_budget_s)
    try:
        report, st, performed = run(cfg, log)
    finally:
        if cfg.time_budget_s and cfg.time_budget_s > 0:
            _clear_alarm()

    text = render(cfg, report, redactor, performed=performed, state=st)
    log.stage(f"report rendered: {report.issues_identified()} issues, "
              f"{report.hashed_files} files hashed")
    if report.errors and not report.actions:
        # pure config/runtime failure, no scan produced anything
        sys.stdout.write(text + "\n")
        return 2
    sys.stdout.write(text + "\n")
    if report.time_budget_hit:
        return 3
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
