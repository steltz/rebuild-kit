#!/usr/bin/env bash
# The L3 acceptance oracle.
#   diff-run.sh --capture-legacy [SET ...]   (re)capture legacy goldens at the pin
#   diff-run.sh --selftest [SET ...]         legacy vs its own goldens (must be 100%)
#   diff-run.sh [SET ...]                    modern vs cached legacy goldens
# SET defaults to t2-core. Reports land in var/report-<set>.json.
set -euo pipefail
HARNESS="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HARNESS/../.." && pwd)"
REPLAY="$ROOT/verification/replay"
RK="$ROOT/workflows/rk/replay.py"
MODE="modern"
case "${1:-}" in
  --capture-legacy) MODE="capture"; shift ;;
  --selftest)       MODE="selftest"; shift ;;
esac
SETS=("${@:-t2-core}")

kill_pid() { [ -f "$1" ] && kill "$(cat "$1")" 2>/dev/null && sleep 0.3 || true; }

drive_side() { # $1 base-url  $2 outbox  $3 state-cmd  $4 mode  $5 in  $6 out  $7 settle
  python3 "$HARNESS/drive.py" --base-url "$1" --outbox "$2" --state-cmd "$3" \
    --email-mode "$4" --input "$5" --out "$6" --settle-ms "$7"
}

fail=0
for SET in "${SETS[@]}"; do
  IN="$REPLAY/input-sets/$SET.jsonl"
  GOLD="$REPLAY/traces/$SET.legacy.jsonl"
  case "$MODE" in
    capture|selftest)
      "$HARNESS/run-legacy.sh" 5091
      OUT="$GOLD"; [ "$MODE" = selftest ] && OUT="$HARNESS/var/$SET.legacy-rerun.jsonl"
      drive_side "http://127.0.0.1:5091" "$HARNESS/var/legacy-run/outbox.jsonl" \
        "python3 $HARNESS/dump_sqlite.py --db $HARNESS/var/legacy-run/db/ticketd.sqlite3" \
        sync "$IN" "$OUT" 0
      kill_pid "$HARNESS/var/legacy-run/server.pid"
      if [ "$MODE" = selftest ]; then
        python3 "$RK" diff --rules "$REPLAY/diff-rules.yaml" \
          --legacy "$GOLD" --modern "$OUT" --out "$HARNESS/var/report-$SET-selftest.json" || fail=1
      fi
      ;;
    modern)
      [ -f "$GOLD" ] || { echo "no golden for $SET — run --capture-legacy first" >&2; exit 1; }
      "$HARNESS/run-modern.sh" 5092
      drive_side "http://127.0.0.1:5092" "$HARNESS/var/modern-run/outbox.jsonl" \
        "$ROOT/modern/harness-dump.sh" queued "$IN" "$HARNESS/var/$SET.modern.jsonl" 300
      kill_pid "$HARNESS/var/modern-run/server.pid"
      python3 "$RK" diff --rules "$REPLAY/diff-rules.yaml" \
        --divergences "$REPLAY/expected-divergences.yaml" \
        --legacy "$GOLD" --modern "$HARNESS/var/$SET.modern.jsonl" \
        --out "$HARNESS/var/report-$SET.json" || fail=1
      ;;
  esac
done
exit $fail
