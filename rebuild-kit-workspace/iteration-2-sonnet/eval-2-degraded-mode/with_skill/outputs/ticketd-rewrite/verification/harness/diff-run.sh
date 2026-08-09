#!/bin/sh
# Twin-boot L3 acceptance oracle. Drives an input set through legacy + modern, diffs responses
# AND post-run state via scripts/replay.py. This is what a WO's L3 verification step calls.
#
# Usage: diff-run.sh <script-name>   e.g. diff-run.sh tickets
#   expects verification/replay/scripts/<script-name>.json to exist.
#
# Caching (T2 workhorse principle, schema.md#input-tiers): legacy golden output is recorded ONCE
# per input set and cached at verification/replay/traces/<name>-legacy.jsonl (the pin makes this
# cache valid indefinitely — legacy/ never changes). The inner loop only re-boots modern/. Pass
# --recapture-legacy to force a fresh legacy run (e.g. after editing a *.json script file).
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NAME="$1"
RECAPTURE_LEGACY=0
if [ "$2" = "--recapture-legacy" ]; then RECAPTURE_LEGACY=1; fi
if [ -z "$NAME" ]; then echo "usage: diff-run.sh <script-name> [--recapture-legacy]" >&2; exit 2; fi

PY="${TICKETD_PYTHON:-python3}"
SCRIPT="$ROOT/verification/replay/scripts/$NAME.json"
LEGACY_TRACE="$ROOT/verification/replay/traces/$NAME-legacy.jsonl"
MODERN_TRACE="$ROOT/verification/replay/traces/$NAME-modern.jsonl"
[ -f "$SCRIPT" ] || { echo "no such script: $SCRIPT" >&2; exit 2; }

if [ ! -f "$LEGACY_TRACE" ] || [ "$RECAPTURE_LEGACY" = "1" ]; then
  echo "[diff-run] capturing legacy goldens for '$NAME' (cache miss or forced)..." >&2
  LEGACY_SCRATCH="/tmp/ticketd-legacy-scratch-$NAME"
  "$ROOT/verification/harness/run-legacy.sh" 5057 "$LEGACY_SCRATCH" &
  LPID=$!
  sleep 1.5
  "$PY" "$ROOT/verification/harness/capture_traces.py" \
    --base-url http://127.0.0.1:5057 --db "$LEGACY_SCRATCH/db/ticketd.sqlite3" \
    --script "$SCRIPT" --out "$LEGACY_TRACE"
  kill "$LPID" 2>/dev/null || true
else
  echo "[diff-run] using cached legacy goldens: $LEGACY_TRACE" >&2
fi

echo "[diff-run] booting modern and capturing traces for '$NAME'..." >&2
if ! "$ROOT/verification/harness/run-modern.sh" >/tmp/run-modern.log 2>&1 & then
  :
fi
MPID=$!
sleep 1
if ! kill -0 "$MPID" 2>/dev/null; then
  echo "[diff-run] modern/ is not runnable yet (pre-M0) — see /tmp/run-modern.log. Nothing to diff." >&2
  exit 2
fi
# (Once modern exists: capture MODERN_TRACE the same way as legacy above, against modern's port,
#  then run the diff below. Left as the next concrete step for whoever lands M0.)
kill "$MPID" 2>/dev/null || true

echo "[diff-run] diffing..." >&2
"$PY" "$ROOT/scripts/replay.py" diff \
  --rules "$ROOT/verification/replay/diff-rules.yaml" \
  --divergences "$ROOT/verification/replay/expected-divergences.yaml" \
  --legacy "$LEGACY_TRACE" --modern "$MODERN_TRACE" \
  --out "$ROOT/verification/replay/traces/$NAME-diff-report.json"
