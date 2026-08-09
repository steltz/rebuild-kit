#!/usr/bin/env bash
# Runs every input-set "suite" under verification/replay/inputs/ against a fresh legacy boot
# and records the golden trace to verification/replay/traces/legacy/<suite>.jsonl.
# T2 goldens are recorded ONCE and cached (schema.md#input-tiers) -- re-run this only when the
# input sets themselves change, or to re-validate the harness (see --self-check below).
#
# Usage: capture-legacy-goldens.sh [--self-check]
#   --self-check: also runs each suite a SECOND time from an independent fresh boot and diffs
#   the two runs against each other (legacy vs itself) -- this is P7's required "run the
#   harness against legacy alone" validation, using scripts/replay.py diff for real.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
H="$ROOT/verification/harness"
INPUTS_DIR="$ROOT/verification/replay/inputs"
OUT_DIR="$ROOT/verification/replay/traces/legacy"
SELF_CHECK="${1:-}"
PORT_BASE=5100

mkdir -p "$OUT_DIR"

i=0
FAILED_SELF_CHECK=0
for input_file in "$INPUTS_DIR"/*.jsonl; do
  suite="$(basename "$input_file" .jsonl)"
  port=$((PORT_BASE + i))
  i=$((i + 1))

  db="$("$H/run-legacy.sh" "$suite" "$port")"
  "$H/drive_inputs.py" --base-url "http://127.0.0.1:$port" --db "$db" \
    --mail-log "$H/.run/legacy-$suite-mail.jsonl" \
    --input "$input_file" --out "$OUT_DIR/$suite.jsonl"
  "$H/stop.sh" legacy "$suite"

  if [ "$SELF_CHECK" = "--self-check" ]; then
    sleep 0.3
    port2=$((port + 500))
    db2="$("$H/run-legacy.sh" "${suite}-check2" "$port2")"
    "$H/drive_inputs.py" --base-url "http://127.0.0.1:$port2" --db "$db2" \
      --mail-log "$H/.run/legacy-${suite}-check2-mail.jsonl" \
      --input "$input_file" --out "$H/.run/${suite}-check2.jsonl"
    "$H/stop.sh" legacy "${suite}-check2"

    echo "--- self-check diff: $suite ---"
    if ! python3 "$H/replay.py" diff \
        --rules "$ROOT/verification/replay/diff-rules.yaml" \
        --legacy "$OUT_DIR/$suite.jsonl" --modern "$H/.run/${suite}-check2.jsonl"; then
      FAILED_SELF_CHECK=1
    fi
  fi
done

if [ "$SELF_CHECK" = "--self-check" ] && [ "$FAILED_SELF_CHECK" -ne 0 ]; then
  echo "SELF-CHECK FAILED: legacy vs. itself produced unexpected diffs -- see above." >&2
  exit 1
fi
echo "Goldens captured -> $OUT_DIR/*.jsonl"
