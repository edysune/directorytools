"""Configuration: argparse CLI flags (with env fallbacks) -> ``Config``.

Every sensitive value (roots, preferred/ignore lists, the Fernet key, the
state dir) is pulled from the environment — never hard-coded in source. The
flags a user might want on the command line mirror the env var names, and
``.env`` is the canonical source in the docker deployment.
"""

from __future__ import annotations
import argparse
import os
from dataclasses import dataclass, field
from typing import List, Optional

from . import paths


def _b(val: Optional[str]) -> bool:
    """Coerce a truthy env/CLI string to bool."""
    if val is None:
        return False
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    # scope (sensitive; from env in practice)
    root: str
    preferred: List[str] = field(default_factory=list)
    excluded: List[str] = field(default_factory=list)
    # behaviour
    dry_run: bool = True
    allow_delete: bool = False
    delete_bad_only: bool = False
    hash_check: bool = False
    corruption_check: bool = False
    encrypt_file_name: bool = False
    bad_file_types: List[str] = field(default_factory=list)
    max_changes: int = 10
    # storage / privacy
    state_dir: str = "/volume/dedup/state"
    secret_key: str = ""
    log_level: str = "INFO"
    # csv file (resolved once in __post_init__)
    state_csv: str = ""

    def __post_init__(self) -> None:
        self.preferred = [paths.normalize(p) for p in (self.preferred or [])]
        self.excluded  = [paths.normalize(p) for p in (self.excluded or [])]
        self.root      = paths.normalize(self.root)
        self.bad_file_types = [
            (ext if ext.startswith(".") else "." + ext).lower()
            for ext in (self.bad_file_types or [])
        ]
        try:
            os.makedirs(self.state_dir, exist_ok=True)
        except OSError:
            # state dir may be read-only in pure dry-run/test contexts; the CSV
            # helpers will surface the error where it matters.
            pass
        self.state_csv = os.path.join(self.state_dir, "dedup_state.csv")

    def deletion_enabled(self) -> bool:
        """The single gate the fixer checks."""
        return (not self.dry_run) and self.allow_delete


def _load_env_file(path: str) -> None:
    """Minimal .env loader (dotenv-free so the container image stays small).

    Sets variables only if not already present in the real environment, so
    docker-compose ``environment:`` values win over the mounted ``.env``.
    """
    if not path or not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)
    except OSError:
        pass


def from_env() -> Config:
    """Build a ``Config`` purely from environment variables."""
    env = os.environ
    return Config(
        root=env.get("DEDUP_ROOT", "/data"),
        preferred=paths.parse_list(env.get("DEDUP_PREFERRED", "")),
        excluded=paths.parse_list(env.get("DEDUP_IGNORE", "")),
        dry_run=_b(env.get("DEDUP_DRY_RUN", "true")),
        allow_delete=_b(env.get("DEDUP_ALLOW_DELETE", "false")),
        delete_bad_only=_b(env.get("DEDUP_DELETE_BAD_ONLY", "false")),
        hash_check=_b(env.get("DEDUP_HASH_CHECK", "false")),
        corruption_check=_b(env.get("DEDUP_CORRUPTION_CHECK", "false")),
        encrypt_file_name=_b(env.get("DEDUP_ENCRYPT_FILE_NAME", "false")),
        bad_file_types=paths.parse_list(env.get("DEDUP_BAD_FILE_TYPES", "")),
        max_changes=int(env.get("DEDUP_MAX_CHANGES", "10")),
        state_dir=env.get("DEDUP_STATE_DIR", "/volume/dedup/state"),
        secret_key=env.get("DEDUP_SECRET_KEY", ""),
        log_level=env.get("DEDUP_LOG_LEVEL", "INFO").upper(),
    )


def from_args(argv=None) -> Config:
    """Build a ``Config`` from CLI flags (flags override env)."""
    ap = argparse.ArgumentParser(prog="dedup_cleaner",
        description="Scan a tree for duplicate files and report; optional "
                    "hashing, corruption checks and name encryption.")
    ap.add_argument("--root", type=str, required=True,
                    help="directory to scan (recursively); required")
    ap.add_argument("--preferred", type=str, default=os.environ.get("DEDUP_PREFERRED", ""),
                    help="space/comma-separated preferred (keeper) roots")
    ap.add_argument("--ignore", type=str, default=os.environ.get("DEDUP_IGNORE", ""),
                    help="space/comma-separated excluded roots (not scanned)")
    ap.add_argument("--dry-run", dest="dry_run", action="store_true", default=None,
                    help="report only; no deletion (default true)")
    ap.add_argument("--dry-off", dest="dry_run_off", action="store_true",
                    help="explicitly disable dry-run (still needs --allow-delete)")
    ap.add_argument("--allow-delete", action="store_true",
                    default=_b(os.environ.get("DEDUP_ALLOW_DELETE", "false")),
                    help="master switch that actually permits deletion")
    ap.add_argument("--delete-bad-only", action="store_true",
                    default=_b(os.environ.get("DEDUP_DELETE_BAD_ONLY", "false")),
                    help="with deletion enabled, only act on bad-file-type "
                         "issues (e.g. .part); never delete dedup-pair members")
    ap.add_argument("--hash-check", action="store_true",
                    default=_b(os.environ.get("DEDUP_HASH_CHECK", "false")),
                    help="confirm name+size dups by SHA-256 byte equality")
    ap.add_argument("--corruption-check", action="store_true",
                    default=_b(os.environ.get("DEDUP_CORRUPTION_CHECK", "false")),
                    help="0-byte + (optional) media probe; persists state CSV")
    ap.add_argument("--encrypt-file-name", action="store_true",
                    default=_b(os.environ.get("DEDUP_ENCRYPT_FILE_NAME", "false")),
                    help="redact file names in logs/CSV; fails fast w/o key")
    ap.add_argument("--bad-file-types", type=str,
                    default=os.environ.get("DEDUP_BAD_FILE_TYPES", ""),
                    help="space/comma-separated bad extensions, e.g. .part")
    ap.add_argument("--max-changes", type=int,
                    default=int(os.environ.get("DEDUP_MAX_CHANGES", "10")))
    ap.add_argument("--state-dir", type=str,
                    default=os.environ.get("DEDUP_STATE_DIR", "/volume/dedup/state"))
    ap.add_argument("--secret-key", type=str,
                    default=os.environ.get("DEDUP_SECRET_KEY", ""))
    ap.add_argument("--log-level", type=str,
                    default=os.environ.get("DEDUP_LOG_LEVEL", "INFO").upper())
    a = ap.parse_args(argv)

    # dry-run default true; --dry-off explicitly turns it off.
    default_dry = os.environ.get("DEDUP_DRY_RUN", "true")
    dry = _b(default_dry) if a.dry_run is None and not a.dry_run_off else (not a.dry_run_off or a.dry_run)

    return Config(
        root=a.root,
        preferred=paths.parse_list(a.preferred),
        excluded=paths.parse_list(a.ignore),
        dry_run=bool(dry),
        allow_delete=bool(a.allow_delete),
        delete_bad_only=bool(a.delete_bad_only),
        hash_check=bool(a.hash_check),
        corruption_check=bool(a.corruption_check),
        encrypt_file_name=bool(a.encrypt_file_name),
        bad_file_types=paths.parse_list(a.bad_file_types),
        max_changes=int(a.max_changes),
        state_dir=a.state_dir,
        secret_key=a.secret_key,
        log_level=a.log_level,
    )
