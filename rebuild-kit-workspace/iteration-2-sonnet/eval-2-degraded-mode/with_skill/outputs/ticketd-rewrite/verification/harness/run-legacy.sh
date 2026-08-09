#!/bin/sh
# Twin-boot: legacy side. Boots the unmodified legacy/ app on a freshly-seeded scratch DB.
# Usage: run-legacy.sh [port] [scratch-dir]
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${1:-5056}"
SCRATCH="${2:-/tmp/ticketd-legacy-scratch}"
PY="${TICKETD_PYTHON:-python3}"

echo "Booting legacy on port $PORT (scratch: $SCRATCH)..." >&2
"$PY" "$ROOT/verification/harness/run_legacy_server.py" \
  --legacy-root "$ROOT/legacy" \
  --scratch "$SCRATCH" \
  --port "$PORT" \
  --seed "$ROOT/verification/harness/seed.sql"
