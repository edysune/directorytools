"""Privacy redaction layer.

When ``DEDUP_ENCRYPT_FILE_NAME`` is on, every file name / path that reaches a
log line or the CSV state store is reduced to an opaque (Fernet) token. The
real name is recoverable only with ``DEDUP_SECRET_KEY`` — never emitted.

Fail-fast contract (spec): if encryption is enabled but no valid key is
available, construction raises ``ConfigKeyError`` and the CLI exits non-zero
*before* scanning, so no raw name is ever produced.
"""

from __future__ import annotations
import sys
import time
from cryptography.fernet import Fernet, InvalidToken


class ConfigKeyError(RuntimeError):
    """Raised when the privacy key is missing/invalid but required."""


class StageLog:
    """Streaming stage logger: one line per milestone, flushed immediately.

    The weekly job runs for tens of minutes on CIFS; without live output an
    outer timeout kill looks identical to a hang. Every line is timestamped
    plus elapsed-seconds so a post-mortem can attribute time to a phase.
    Paths entering these lines MUST already be redacted by the caller.
    """

    def __init__(self, stream=None, enabled: bool = True):
        self._t0 = time.monotonic()
        self._stream = stream if stream is not None else sys.stdout
        self.enabled = enabled

    def stage(self, msg: str) -> None:
        if not self.enabled:
            return
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        try:
            self._stream.write(
                f"[dedup_cleaner {ts}Z +{time.monotonic() - self._t0:8.1f}s] {msg}\n")
            self._stream.flush()
        except Exception:  # logging must never be the thing that crashes a run
            pass

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._t0


class Redactor:
    def __init__(self, enabled: bool, key: str):
        self._requested = bool(enabled)
        self._fernet = None
        if enabled:
            key = (key or "").strip()
            if not key:
                raise ConfigKeyError(
                    "DEDUP_ENCRYPT_FILE_NAME is enabled but DEDUP_SECRET_KEY is "
                    "empty; refusing to emit raw file names. Set DEDUP_SECRET_KEY "
                    "or disable name encryption.")
            try:
                self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
            except Exception as exc:  # pragma: no cover - depends on key shape
                raise ConfigKeyError(
                    f"DEDUP_SECRET_KEY is not a valid Fernet key: {exc}")
        self.enabled = self._fernet is not None

    # -- for log/report lines: short, human-unusable token -----------------
    def display(self, value: str) -> str:
        if not self.enabled:
            return value
        tok = self.token(value)
        return tok[:16] + "…"

    # -- for the CSV state store: full reversible ciphertext ---------------
    def token(self, value: str) -> str:
        if not self.enabled:
            return value
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def try_decrypt(self, token: str):
        """Decipher a stored token; raise ``InvalidToken`` if the key differs."""
        if not self.enabled:
            return token
        if isinstance(token, bytes):
            token = token.decode("ascii")
        return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
