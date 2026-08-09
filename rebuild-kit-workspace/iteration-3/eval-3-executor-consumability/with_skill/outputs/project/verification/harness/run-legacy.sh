#!/usr/bin/env bash
# Boots the legacy ticketd app for real (see legacy_wrapper.py for how -- fresh sqlite seeded
# from verification/replay/corpus/seed.sql, SMTP stubbed to a local JSONL mail log, no legacy/
# file touched). One instance per input-set "suite" for hermetic replay sets: each suite gets
# its own scratch run dir + port so suites never see each other's mutations.
#
# Usage: run-legacy.sh <suite-name> <port>
#   starts the server in the background, prints its PID, waits for it to answer.
# Requires: Flask installed for the Python interpreter this runs under (the legacy app's only
# non-stdlib dependency). If you don't have it project-wide, `pip install flask` in a venv and
# invoke this script with that venv's python on PATH -- see README.md in this directory.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SUITE="${1:?usage: run-legacy.sh <suite-name> <port>}"
PORT="${2:?usage: run-legacy.sh <suite-name> <port>}"
RUN_DIR="$ROOT/verification/harness/.run/legacy-$SUITE"
MAIL_LOG="$ROOT/verification/harness/.run/legacy-$SUITE-mail.jsonl"
PID_FILE="$ROOT/verification/harness/.run/legacy-$SUITE.pid"

rm -rf "$RUN_DIR"
mkdir -p "$RUN_DIR"
: > "$MAIL_LOG"

LEGACY_DIR="$(python3 -c "import json;print(json.load(open('$ROOT/rebuild.json'))['layout']['legacy_dir'])")"

python3 "$ROOT/verification/harness/legacy_wrapper.py" \
  --legacy-root "$ROOT/$LEGACY_DIR" \
  --run-dir "$RUN_DIR" \
  --mail-log "$MAIL_LOG" \
  --seed "$ROOT/verification/replay/corpus/seed.sql" \
  --port "$PORT" > "$ROOT/verification/harness/.run/legacy-$SUITE-boot.log" 2>&1 &
echo $! > "$PID_FILE"

for _ in $(seq 1 30); do
  if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/tickets"; then
    echo "legacy [$SUITE] up on :$PORT (pid $(cat "$PID_FILE"))" >&2
    echo "$RUN_DIR/db/ticketd.sqlite3"   # ONLY machine-readable output on stdout
    exit 0
  fi
  sleep 0.3
done
echo "legacy [$SUITE] failed to boot -- see verification/harness/.run/legacy-$SUITE-boot.log" >&2
cat "$ROOT/verification/harness/.run/legacy-$SUITE-boot.log" >&2
exit 1
