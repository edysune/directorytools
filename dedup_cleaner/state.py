"""Cross-run persistence for the corruption/hash check (additive feature).

Rows are keyed by a *non-reversible* digest of ``name|path`` (so the raw name
never has to live on disk), and the name/path cells are Fernet-encrypted when
the privacy layer is on (plaintext only if the user explicitly disabled it).

Load -> add/update -> prune-stale -> save keeps the CSV stable across weekly
runs: unchanged size+hash entries are not re-processed, directories that no
longer exist are pruned, and new files are appended.
"""

from __future__ import annotations
import csv
import hashlib
import os
from typing import Dict, Iterable, Set

from .logs import Redactor
from .models import FileInfo


_COLS = ["id", "dirid", "size", "sha", "name", "path"]


def _digest(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


class State:
    def __init__(self, redactor: Redactor):
        self.redactor = redactor
        self.rows: Dict[str, dict] = {}
        self.warnings: list = []
        self.decryption_ok = True

    # -- tokenisation ------------------------------------------------------
    def _tokens(self, name: str, path: str):
        if self.redactor.enabled:
            return self.redactor.token(name), self.redactor.token(path)
        return name, path

    @classmethod
    def load(cls, csv_path: str, redactor: Redactor) -> "State":
        st = cls(redactor)
        if not csv_path or not os.path.isfile(csv_path):
            return st
        try:
            with open(csv_path, newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    rid = (r.get("id") or "").strip()
                    if rid:
                        st.rows[rid] = r
        except Exception as exc:  # unreadable -> treat as fresh, warn
            st.decryption_ok = False
            st.rows = {}
            st.warnings.append(f"could not read state CSV ({exc}); starting fresh")
        return st

    def verify_decryption(self, sample_rows: int = 3) -> bool:
        """Prove the key can still read the stored tokens (best-effort).

        Returns True on success; on the first failure it sets
        ``decryption_ok=False`` and the caller should skip SHA-hash validation.
        """
        if not self.redactor.enabled:
            return True
        for row in list(self.rows.values())[:sample_rows]:
            for col in ("name", "path"):
                val = row.get(col) or ""
                if not val:
                    continue
                try:
                    self.redactor.try_decrypt(val)
                except Exception:
                    self.decryption_ok = False
                    self.warnings.append(
                        "state CSV decrypt failed — SHA-hash validation disabled for this run")
                    return False
        return True

    # -- mutation ----------------------------------------------------------
    def add_or_update(self, info: FileInfo, sha: str = "") -> bool:
        """Insert/update one file. Returns True if a NEW row was written
        (or size/sha changed); False if it was unchanged (skip re-processing)."""
        fid = _digest(info.name, info.path)
        dirid = _digest(os.path.dirname(info.path))
        existing = self.rows.get(fid)
        if (existing and existing.get("size") == str(info.size)
                and sha and existing.get("sha") == sha):
            return False
        name_tok, path_tok = self._tokens(info.name, info.path)
        self.rows[fid] = {
            "id": fid,
            "dirid": dirid,
            "size": str(info.size),
            "sha": sha or (existing or {}).get("sha", ""),
            "name": name_tok,
            "path": path_tok,
        }
        return True

    def prune_stale(self, known_dirids: Iterable[str]) -> int:
        """Drop entries whose directory was not seen this run. Returns removed."""
        keep = {d for d in known_dirids}
        removed = sum(1 for rid, row in self.rows.items()
                      if row.get("dirid") not in keep)
        self.rows = {
            rid: row for rid, row in self.rows.items()
            if row.get("dirid") in keep
        }
        return removed

    def save(self, csv_path: str) -> None:
        d = os.path.dirname(csv_path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=_COLS)
            w.writeheader()
            for rid in sorted(self.rows):
                w.writerow({c: self.rows[rid].get(c, "") for c in _COLS})

    def process(self, info, hasher) -> bool:
        """One-file state update: hash-if-needed + store.  Returns True when a
        new row was written or size/sha changed; False when unchanged."""
        fid = _digest(info.name, info.path)
        dirid = _digest(os.path.dirname(info.path))
        existing = self.rows.get(fid)
        size_changed = existing is None or existing.get("size") != str(info.size)
        sha = ""
        if size_changed:
            # size changed (or new) -- re-hash; unchanged -> skip hash cost
            if hasher is not None:
                try:
                    sha = hasher(info.path)
                except OSError:
                    sha = ""
            name_tok, path_tok = self._tokens(info.name, info.path)
            self.rows[fid] = {"id": fid, "dirid": dirid, "size": str(info.size),
                              "sha": sha, "name": name_tok, "path": path_tok}
            return True
        # size unchanged: keep existing sha; no hash needed
        return False

    def should_track_size(self, info) -> bool:
        """True if this file needs a fresh row added (new or size-changed) --
        used by cli to decide hash cost."""
        fid = _digest(info.name, info.path)
        e = self.rows.get(fid)
        return e is None or e.get("size") != str(info.size)

    def __len__(self) -> int:
        return len(self.rows)
