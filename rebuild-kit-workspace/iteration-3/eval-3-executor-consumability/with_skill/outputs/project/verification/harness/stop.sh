#!/usr/bin/env bash
# Stops a legacy/modern instance started by run-legacy.sh / run-modern.sh for <suite-name>.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SIDE="${1:?usage: stop.sh <legacy|modern> <suite-name>}"
SUITE="${2:?usage: stop.sh <legacy|modern> <suite-name>}"
PID_FILE="$ROOT/verification/harness/.run/$SIDE-$SUITE.pid"
if [ -f "$PID_FILE" ]; then
  kill "$(cat "$PID_FILE")" 2>/dev/null || true
  rm -f "$PID_FILE"
fi

# modern/ additionally owns a scratch Postgres cluster (run-modern.sh) -- no-op for legacy,
# which never writes this marker.
PGDATA_MARKER="$ROOT/verification/harness/.run/$SIDE-$SUITE.pgdata"
if [ -f "$PGDATA_MARKER" ]; then
  pg_ctl -D "$(cat "$PGDATA_MARKER")" stop -m fast >/dev/null 2>&1 || true
  rm -f "$PGDATA_MARKER"
fi
