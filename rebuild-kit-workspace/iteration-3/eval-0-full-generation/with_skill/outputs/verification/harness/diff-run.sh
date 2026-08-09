#!/bin/sh
# Twin-boot differential replay -- the L3 acceptance oracle. Boots both trees, drives a named
# input set through both, diffs via scripts/replay.py. This is what a WO's L3 verification step
# (root CLAUDE.md executor loop, step 4) actually runs.
#
# Usage: verification/harness/diff-run.sh <trace-basename>
#   e.g. verification/harness/diff-run.sh tickets-crud
#        (reads verification/replay/traces/tickets-crud.jsonl as the input/expected-request set)
#
# Exit code: 0 = all pass, 1 = failures (propagated from scripts/replay.py diff), 2 = setup error.
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SKILL_SCRIPTS="${TICKETD_SKILL_SCRIPTS:-}"
NAME="${1:?usage: diff-run.sh <trace-basename>}"
TRACE_FILE="$ROOT/verification/replay/traces/$NAME.jsonl"

if [ ! -f "$TRACE_FILE" ]; then
  echo "diff-run.sh: no trace file at $TRACE_FILE" >&2
  exit 2
fi
if [ -z "$SKILL_SCRIPTS" ] || [ ! -f "$SKILL_SCRIPTS/replay.py" ]; then
  echo "diff-run.sh: set TICKETD_SKILL_SCRIPTS to the rebuild-kit skill's scripts/ dir (contains replay.py)." >&2
  echo "This harness does not vendor replay.py -- it's the skill's, run from wherever the skill lives." >&2
  exit 2
fi

echo "diff-run.sh: this drives $TRACE_FILE's *requests* through a live modern boot and compares" >&2
echo "the *live modern responses* against the trace's captured legacy responses. It does NOT" >&2
echo "re-boot legacy (the trace file already IS legacy's golden output per input-tier T2, schema.md)" >&2
echo "-- that's the whole point of caching goldens: the inner loop boots only modern. To regenerate" >&2
echo "legacy goldens themselves (e.g. after a legacy re-pin), re-run the capture procedure documented" >&2
echo "in verification/harness/run-legacy.sh's header and P7's playbook, not this script." >&2

# --- boot modern, drive the trace file's requests through it, capture responses ---
"$ROOT/verification/harness/run-modern.sh" 5100 &
MODERN_PID=$!
cleanup() { kill "$MODERN_PID" 2>/dev/null || true; }
trap cleanup EXIT
sleep 2

MODERN_OUT="$(mktemp /tmp/ticketd-modern-trace.XXXXXX.jsonl)"
python3 "$ROOT/verification/harness/drive_trace.py" \
  --base-url "http://127.0.0.1:5100" \
  --in "$TRACE_FILE" \
  --out "$MODERN_OUT"

python3 "$SKILL_SCRIPTS/replay.py" diff \
  --rules "$ROOT/verification/replay/diff-rules.yaml" \
  --divergences "$ROOT/verification/replay/expected-divergences.yaml" \
  --legacy "$TRACE_FILE" \
  --modern "$MODERN_OUT" \
  --out "$ROOT/verification/replay/last-diff-report.json"
CODE=$?
rm -f "$MODERN_OUT"
exit $CODE
