#!/usr/bin/env bash
# The acceptance oracle (L3). Boots both trees, then diffs every feature's traces.
# Legacy goldens are cached (verification/replay/traces/*.legacy.jsonl, committed) — this
# script only regenerates them if --refresh-legacy is passed; the inner loop boots modern only.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CORPUS_DIR="$ROOT/verification/replay/corpus"
TRACES_DIR="$ROOT/verification/replay/traces"
RULES="$ROOT/verification/replay/diff-rules.yaml"
DIVERGENCES="$ROOT/verification/replay/expected-divergences.yaml"

if [[ "${1:-}" == "--refresh-legacy" ]]; then
  "$ROOT/verification/harness/run-legacy.sh"
fi
"$ROOT/verification/harness/run-modern.sh"

overall_pass=0
overall_fail=0
for cf in "$CORPUS_DIR"/*.requests.jsonl; do
  feature="$(basename "$cf" .requests.jsonl)"
  legacy_trace="$TRACES_DIR/$feature.legacy.jsonl"
  modern_trace="$TRACES_DIR/$feature.modern.jsonl"
  if [[ ! -f "$legacy_trace" ]]; then
    echo "MISSING legacy golden for $feature — run: $ROOT/verification/harness/run-legacy.sh"
    exit 1
  fi
  echo "=== $feature ==="
  set +e
  python3 "$ROOT/verification/harness/replay.py" diff --rules "$RULES" --divergences "$DIVERGENCES" \
    --legacy "$legacy_trace" --modern "$modern_trace" \
    --out "$ROOT/verification/replay/${feature}.report.json"
  status=$?
  set -e
  if [[ $status -ne 0 ]]; then overall_fail=1; fi
done

if [[ $overall_fail -ne 0 ]]; then
  echo "One or more features failed L3 replay. See verification/replay/*.report.json."
  exit 1
fi
echo "All features pass L3 replay."
