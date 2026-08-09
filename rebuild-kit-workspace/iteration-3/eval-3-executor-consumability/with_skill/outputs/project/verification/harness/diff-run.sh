#!/usr/bin/env bash
# The L3 acceptance oracle (root CLAUDE.md refers to this exact script). For a given suite
# (one WO's acceptance.replay_set), boots modern fresh, drives the same input set that produced
# the cached legacy golden, and diffs the two traces under diff-rules.yaml +
# expected-divergences.yaml. Legacy is NOT re-booted per the schema.md T2 design ("legacy
# golden outputs recorded once per input set and cached ... the inner loop boots only modern")
# -- pass --refresh-legacy to force a re-capture first (e.g. after a spec-patch changes an
# input set).
#
# Usage: diff-run.sh <suite-name> [--refresh-legacy]
# Exit code: 0 = all traces pass (mirrors scripts/replay.py diff's own exit code). 1 = failures.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
H="$ROOT/verification/harness"
SUITE="${1:?usage: diff-run.sh <suite-name> [--refresh-legacy]}"
REFRESH="${2:-}"

GOLDEN="$ROOT/verification/replay/traces/legacy/$SUITE.jsonl"
INPUT="$ROOT/verification/replay/inputs/$SUITE.jsonl"

if [ "$REFRESH" = "--refresh-legacy" ] || [ ! -f "$GOLDEN" ]; then
  echo "[diff-run] (re-)capturing legacy golden for $SUITE" >&2
  db="$("$H/run-legacy.sh" "$SUITE" 5900)"
  "$H/drive_inputs.py" --base-url "http://127.0.0.1:5900" --db "$db" \
    --mail-log "$H/.run/legacy-$SUITE-mail.jsonl" --input "$INPUT" --out "$GOLDEN"
  "$H/stop.sh" legacy "$SUITE"
fi

echo "[diff-run] booting modern for $SUITE" >&2
mdb="$("$H/run-modern.sh" "$SUITE" 5901)"
"$H/drive_inputs.py" --base-url "http://127.0.0.1:5901" --db "$mdb" \
  --mail-log "$H/.run/modern-$SUITE-mail.jsonl" --input "$INPUT" \
  --out "$H/.run/modern-$SUITE.jsonl"
"$H/stop.sh" modern "$SUITE"

echo "[diff-run] diffing $SUITE" >&2
python3 "$H/replay.py" diff \
  --rules "$ROOT/verification/replay/diff-rules.yaml" \
  --divergences "$ROOT/verification/replay/expected-divergences.yaml" \
  --legacy "$GOLDEN" --modern "$H/.run/modern-$SUITE.jsonl" \
  --out "$ROOT/verification/replay/traces/last-diff-$SUITE.json"
