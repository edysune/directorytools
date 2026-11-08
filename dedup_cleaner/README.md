# dedup_cleaner

A privacy-guarded, **dry-run-first** file de-duplicator + cleaner for a NAS
tree. It finds likely-duplicate files (same **name + byte size**, optionally
confirmed by **SHA-256**), applies structured keep/drop rules, flags
"bad" trailing files (e.g. `.part`), and reports how much space it *could*
recover. It is designed to be run as a weekly Docker job.

The tool is deliberately **conservative**: it will not delete anything it
cannot resolve with a rule, and it cannot delete at all unless you flip two
independent switches.

---

## Safety model (read this first)

| Control | Default | Meaning |
|---|---|---|
| `DEDUP_DRY_RUN` | `true` | Report only. No file is ever touched. |
| `DEDUP_ALLOW_DELETE` | `false` | **Master switch for deletion.** |
| deletion | off | `os.remove` runs **only** when `dry_run is False` **AND** `allow_delete is True`. |

With the shipped defaults (both off), a run is read-only regardless of any
bug in the decision logic. To actually delete, you must explicitly set
`DEDUP_DRY_RUN=false` **and** `DEDUP_ALLOW_DELETE=true` in your `.env`.

Additional safeguards:

- **Preferred paths are ranked, and the stronger copy keeps.** The
  `DEDUP_PREFERRED` list is an order of strength: e.g. `Models` before
  `Categories` means the `Models` copy wins the tie and the `Categories` copy
  becomes the removal candidate. A non-preferred copy always loses to any
  preferred copy. A file is never removed in favour of an equal- or
  lower-ranked one.
- **Ambiguity = skip.** If no copy is preferred, *or several copies share the
  top rank* (tied at equal weight), the group is skipped — nothing is removed,
  but it is still counted toward the `max_changes` cap.
- **Bad file types** (e.g. `.part`) are flagged and targeted regardless of
  preference; still dry-run-gated.
- **`max_changes` cap** (default 10) stops the scan early once that many
  issues (resolved *or* ambiguous) are identified, so it never crawls terabytes
  before it acts.
- **No real values in code.** Every sensitive value (roots, preferred/ignore
  lists, the Fernet key, the state dir) comes from `.env` (git-ignored).
  Only `.env.example` is checked in, and it uses placeholders.

---

## What it does, step by step

1. **Scan** the root recursively (skipping excluded dirs), recording each
   file's name, absolute path, and byte size into a fast `(name, size)` map.
2. **State load** (only if `hash_check` or `corruption_check` is on): read the
   previous run's CSV so unchanged files need no re-hash.
3. **Dedup rules** per name+size group (respecting the `max_changes` cap).
4. **Bad-type** scan (cheap, unambiguous).
5. **Corruption** scan (additive): zero-byte files + an optional media probe.
6. **State persist**: store new/changed rows, prune dirs that no longer exist.
7. **Fix stage** (only if deletion is enabled).
8. **Report**: scanned counts, issues found, actions, warnings, and space to
   recover — with every path shown through the redactor.

### Privacy (`DEDUP_ENCRYPT_FILE_NAME`)
When enabled, file names and paths in logs and in the state CSV are stored as
opaque Fernet tokens using `DEDUP_SECRET_KEY`. If this is enabled but the key
is missing/invalid, the tool **fails fast** (refuses to run) rather than risk
logging raw names. If it ever loads a CSV it cannot decrypt, it warns and skips
SHA-hash validation for that run (per spec) instead of crashing.

---

## Running it

### Locally (dev)
```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"           # or: pip install -r requirements.txt

export DEDUP_ROOT=/path/to/scan   # all DEDUP_* come from env or flags
python -m dedup_cleaner --root "$DEDUP_ROOT" \
    --preferred /path/to/keeper --ignore /path/to/skip \
    --corruption-check --encrypt-file-name
```
Or via the tools wrapper: `python tools/dedup_cleaner.py --root ". ..."`

`--dry-run` (default) leaves everything untouched. To review the plan, just read
the report.

### Flags (all optional; env-var defaults apply)
```
--root PATH            (required) directory to scan
--preferred PATH[ PATH]  keeper roots (never deleted)
--ignore PATH[ PATH]    excluded roots (not scanned)
--dry-run / --dry-off  report vs. attempt
--allow-delete          master switch for deletion
--hash-check            confirm dups by SHA-256 byte-equality
--corruption-check      0-byte + media probe + persist state CSV
--encrypt-file-name     redact names/paths (needs --secret-key or DEDUP_SECRET_KEY)
--bad-file-types EXT..  e.g. .part
--max-changes N         default 10
--state-dir PATH        where dedup_state.csv lives
--secret-key FERNET     Fernet key (or DEDUP_SECRET_KEY)
--log-level LEVEL
```

### Docker (recommended)
```bash
docker build -t dedup_cleaner:0.1.0 .
docker run --rm --env-file .env \
  -v "${DEDUP_ROOT}:/data:rw" \
  -v dedup-state:/volume/dedup/state \
  dedup_cleaner:0.1.0 --root /data
```
See [`deploy/dedup-cleaner.compose.yml`](../deploy/dedup-cleaner.compose.yml)
for the paste-ready compose service and the Monday-night cron line.

---

## Testing

The rule engine, scanner, hashing, state persistence, and privacy redactor are
unit-tested. Coverage is enforced at **85%** (currently ~93%):

```bash
pip install -e ".[dev]"
pytest                      # runs with --cov-fail-under=85 from pyproject
```
The deletion path is tested explicitly in **both** safe states (guard holds)
and the fully-enabled state, so the two-switch design is proven, not assumed.

---

## Configuration template
Copy `.env.example` (repo root) to a git-ignored `.env` and fill in real
values. The Fernet key can be generated with:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
