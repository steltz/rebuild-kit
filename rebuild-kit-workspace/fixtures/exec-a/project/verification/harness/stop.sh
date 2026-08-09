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
