#!/usr/bin/env bash
# L3 twin-boot differential replay — the acceptance oracle.
#
# Usage:
#   diff-run.sh --capture-goldens [SET]   record legacy golden traces (pinned ref) once
#   diff-run.sh [SET]                     drive modern, diff against cached goldens
#   FRESH_LEGACY=1 diff-run.sh [SET]      re-boot legacy instead of using cached goldens
# SET defaults to 'core' (verification/replay/input-sets/<SET>.jsonl).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
REPLAY="$ROOT/verification/replay"

MODE=diff
if [ "${1:-}" = "--capture-goldens" ]; then MODE=capture; shift; fi
SET="${1:-core}"
INPUT="$REPLAY/input-sets/$SET.jsonl"
GOLDEN="$REPLAY/traces/$SET.legacy.jsonl"
[ -f "$INPUT" ] || { echo "no input set: $INPUT" >&2; exit 1; }

capture_legacy() {
  eval "$("$HERE/run-legacy.sh")"
  trap 'kill $LEGACY_PIDS 2>/dev/null || true' EXIT
  python3 "$HERE/drive.py" --base-url "$LEGACY_BASE_URL" --input-set "$INPUT" \
    --emails-from "file:$LEGACY_SMTP_LOG" --db "$LEGACY_DB" --out "$1"
  kill $LEGACY_PIDS 2>/dev/null || true
  trap - EXIT
}

if [ "$MODE" = capture ]; then
  mkdir -p "$REPLAY/traces"
  capture_legacy "$GOLDEN"
  echo "goldens recorded at pinned ref → $GOLDEN"
  exit 0
fi

LEGACY_TRACES="$GOLDEN"
if [ "${FRESH_LEGACY:-0}" = "1" ] || [ ! -f "$GOLDEN" ]; then
  LEGACY_TRACES="$(mktemp /tmp/legacy-traces.XXXXXX.jsonl)"
  capture_legacy "$LEGACY_TRACES"
fi

eval "$("$HERE/run-modern.sh")"
trap 'kill $MODERN_PIDS 2>/dev/null || true' EXIT
MODERN_TRACES="$(mktemp /tmp/modern-traces.XXXXXX.jsonl)"
python3 "$HERE/drive.py" --base-url "$MODERN_BASE_URL" --input-set "$INPUT" \
  --emails-from "url:$MODERN_BASE_URL/__harness__/emails" \
  --state-url "$MODERN_BASE_URL/__harness__/state" --out "$MODERN_TRACES"
kill $MODERN_PIDS 2>/dev/null || true
trap - EXIT

python3 "$HERE/replay.py" diff --rules "$REPLAY/diff-rules.yaml" \
  --divergences "$REPLAY/expected-divergences.yaml" \
  --legacy "$LEGACY_TRACES" --modern "$MODERN_TRACES" \
  --out "$REPLAY/report.json"
