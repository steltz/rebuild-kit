#!/usr/bin/env bash
# Boot the modern tree for twin-boot replay. CONTRACT (WO-001 implements it):
#   - `modern/harness-boot.sh PORT SINK_FILE` must: create a fresh Postgres (or embedded
#     equivalent) schema from docs/migration/target-schema.sql, seed it with the logical
#     content of verification/replay/fixtures/seed.sql (modern mapping), start the app on
#     PORT with its mail dispatcher delivering to SINK_FILE (mail-message.schema.json JSON
#     lines), and FLUSH the outbox worker synchronously when POST /__harness/flush-mail is
#     hit — drive.py samples the sink after each request (--settle-ms covers the gap).
#   - `modern/harness-dump.sh` must print the DB as JSON in dump_sqlite.py's shape.
#   - Harness-only endpoints/hooks must be enabled by an env flag the harness sets
#     (HARNESS=1) and be absent in production builds.
# Usage: run-modern.sh [PORT]          (default 5092)
set -euo pipefail
HARNESS="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HARNESS/../.." && pwd)"
MODERN_DIR="$(python3 -c "import json;print(json.load(open('$ROOT/rebuild.json'))['layout']['modern_dir'])")"
PORT="${1:-5092}"
RUN="$HARNESS/var/modern-run"

if [ ! -x "$ROOT/$MODERN_DIR/harness-boot.sh" ]; then
  echo "modern tree has no harness-boot.sh yet — WO-001 (walking skeleton) creates it." >&2
  echo "Until then L3 cannot run; L1/L2 still can. See verification/harness/README.md." >&2
  exit 2
fi

rm -rf "$RUN"; mkdir -p "$RUN"
HARNESS=1 "$ROOT/$MODERN_DIR/harness-boot.sh" "$PORT" "$RUN/outbox.jsonl" &
echo $! > "$RUN/server.pid"
for i in $(seq 1 100); do
  if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/tickets"; then
    echo "modern up on :$PORT (pid $(cat "$RUN/server.pid"))"; exit 0
  fi
  sleep 0.2
done
echo "modern failed to boot" >&2; exit 1
