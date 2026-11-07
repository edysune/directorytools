"""dedup_cleaner: scan a directory tree for duplicate files by name+size and
(when enabled) confirm by hash, apply structured keep/drop rules, and report.

Design goals
------------
* **Privacy by default.** Real paths/names are only ever produced as raw data
  when the privacy layer is OFF; when ``DEDUP_ENCRYPT_FILE_NAME`` is on they are
  reduced to opaque (Fernet) tokens in every log/report line and in the CSV
  state store.
* **Safety.** Deletion is a no-op unless BOTH ``dry_run`` is false AND the
  separate master switch ``allow_delete`` is true. Preferred paths are never
  deleted. Two independent tripwires guard against accidental data loss.
* **Additive features.** Hashing, corruption checks, and name encryption are
  only wired in when enabled; the core (name+size) dedup always works.
"""

__version__ = "0.1.0"
