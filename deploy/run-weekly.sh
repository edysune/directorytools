#!/usr/bin/env bash
# Weekly dedup_cleaner job (run by cron, Monday).
#
# Self-locating: uses whatever directory it lives in as the compose project,
# so the same script works in the repo (deploy/) and on the deploy box.
#
# Mode comes from the project's compose/.env on the deploy box — NOT from this
# script. Current live setting on .236: DEDUP_DRY_RUN=false +
# DEDUP_ALLOW_DELETE=true (hash-confirmed duplicate copies ARE deleted;
# see the 2026-11-12 first live run). This script itself adds NO deletion
# logic — flipping flags in /docker/dedup-cleaner/.env changes what the NEXT
# scheduled run does.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

LOG_DIR="${DEDUP_LOG_DIR:-$PROJECT_DIR/logs}"
mkdir -p "$LOG_DIR"

STAMP="$(date +%F_%H%M)"
LOG="$LOG_DIR/${STAMP}_dedup_cleaner.log"

echo "=== dedup_cleaner run: $STAMP (project: $PROJECT_DIR) ===" | tee -a "$LOG"

# Bounded three ways: DEDUP_MAX_CHANGES (work), DEDUP_TIME_BUDGET_S (in-
# container wall clock: clean self-exit + state save + partial report), and
# the host `timeout` (last resort; kept LONGER than the budget so it never
# has to fire on a live run — when IT fires, the log has no end-report and
# we learn nothing, which is exactly the 2026-11-11 incident).
# Outer backstop = the pinned in-container budget (4h) + 10min grace.
timeout "${DEDUP_RUN_TIMEOUT:-15000}" docker compose run --rm --no-deps dedup_cleaner \
  >> "$LOG" 2>&1
rc=$?
if [ "$rc" -ne 0 ]; then
  echo "dedup_cleaner exited non-zero (code $rc) — see log above." | tee -a "$LOG"
  exit "$rc"
fi

# Keep the most recent 30 logs.
ls -1t "$LOG_DIR"/*.log 2>/dev/null | tail -n +31 | xargs -r rm -f --

echo "--- run summary (first 25 lines) ---"
sed -n '1,25p' "$LOG"
echo "=== done; log=$LOG rc=$rc ==="
