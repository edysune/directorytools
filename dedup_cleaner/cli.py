"""Orchestrator: config -> scan -> dedup -> fix -> report.

Kept dependency-free (stdlib + ``cryptography``) so the container is small.
"""

from __future__ import annotations

import os
import sys
from typing import List

from . import scanner, dedup as dedup_rules, hashing
from .config import Config, from_args, from_env, _load_env_file
from .fixer import apply as apply_deletions
from .logs import Redactor, ConfigKeyError
from .media import is_media, probe_media
from .models import RunReport
from .report import render
from .state import State


def _hasher_for(report: RunReport):
    """Return ``path -> sha256`` that hashes each file at most ONCE per run.

    A file may be requested by both the dedup confirmation pass and the state
    cache loop; without a memo it would be read twice from (possibly network)
    storage. ``report.hashed_files`` counts real I/O, so it increments once.
    """
    memo: dict = {}
    def hasher(path: str) -> str:
        if path not in memo:
            memo[path] = hashing.sha256_file(path)
            report.hashed_files += 1
        return memo[path]
    return hasher


def run(cfg: Config) -> "tuple[RunReport, State|None, List[str]]":
    """Execute one scan + clean pass.  Returns ``(report, state, performed)``."""
    report = RunReport()

    # privacy fail-fast: constructing the Redactor raises ConfigKeyError if
    # enabled without a valid key -- we catch it here and surface it cleanly.
    redactor = Redactor(cfg.encrypt_file_name, cfg.secret_key)

    root = cfg.root
    if not os.path.isdir(root):
        report.errors.append(f"root directory not found: {redactor.display(root)}")
        return report, None, []

    # 1) scan ---------------------------------------------------------------
    files = list(scanner.iter_files(root, cfg.excluded))
    by_ns, by_sz, total_bytes = scanner.build_indexes(files)
    report.scanned_files = len(files)
    report.scanned_bytes = total_bytes
    report.groups_examined = sum(1 for m in by_ns.values() if len(m) >= 2)

    # 2) state (additive; loaded BEFORE decisions so unchanged files are cheap)
    use_state = cfg.corruption_check or cfg.hash_check
    st = None
    hasher = None
    if use_state:
        st = State.load(cfg.state_csv, redactor)
        if cfg.hash_check or cfg.corruption_check:
            if not st.verify_decryption():
                # spec: on decrypt failure, skip SHA-hash validation for this run
                cfg.hash_check = False
        if cfg.hash_check:
            hasher = _hasher_for(report)

    # 3) optional sha-confirmation callable (only if hash_check on)
    confirm = None
    if cfg.hash_check:
        confirm = hashing.confirm_equal   # keeper, victims -> confirmed victims

    # 4) dedup group decisions (respect cap; ambiguity counts)
    actions, stopped_by_cap = dedup_rules.plan_dedup(
        by_ns, cfg.preferred, cfg.max_changes, confirm=confirm)
    report.actions.extend(actions)
    report.stopped_by_cap = stopped_by_cap

    # 5) bad file types (no cap -- cheap, unambiguous "delete .part" style)
    report.actions.extend(dedup_rules.find_bad_type_files(files, cfg.bad_file_types))

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
            for f in files:
                if id(f) in candidate_ids and st.should_track_size(f):
                    st.process(f, hasher)
        else:
            for f in files:
                st.process(f, hasher)  # size-only tracking (no hash cost)
        known_dirids = {_digest_dirinfo(f.path) for f in files}
        st.prune_stale(known_dirids)
        try:
            st.save(cfg.state_csv)
        except OSError as exc:
            report.warnings.append(f"state save failed: {exc}")

    # 8) fix stage (gated by dry_run off AND allow_delete on)
    performed = apply_deletions(cfg, report, redactor)
    return report, st, performed


def _digest_dirinfo(path: str) -> str:
    """sha256 of the containing directory; matches State's ``dirid`` space."""
    from .state import _digest
    return _digest(os.path.dirname(path))


def main(argv=None) -> int:
    """Entry point.  Returns a process exit code (0 clean, 1 config, 2 error)."""
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
        _ = Redactor(cfg.encrypt_file_name, cfg.secret_key)
    except ConfigKeyError as exc:
        sys.stderr.write(f"[dedup_cleaner] config error: {exc}\n")
        return 1

    report, st, performed = run(cfg)
    text = render(cfg, report, Redactor(cfg.encrypt_file_name, cfg.secret_key),
                  performed=performed, state=st)
    if report.errors and not report.actions:
        # pure config/runtime failure, no scan produced anything
        sys.stdout.write(text + "\n")
        return 2
    sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
