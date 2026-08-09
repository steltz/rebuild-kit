#!/usr/bin/env bash
# Boot the pinned legacy tree on a fresh seeded DB with the SMTP capture sink.
# Usage: run-legacy.sh [PORT]          (default 5091)
# Emits: var/legacy-run/{db/ticketd.sqlite3, outbox.jsonl, server.pid}
set -euo pipefail
HARNESS="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HARNESS/../.." && pwd)"
LEGACY_DIR="$(python3 -c "import json;print(json.load(open('$ROOT/rebuild.json'))['layout']['legacy_dir'])")"
PORT="${1:-5091}"
VENV="$HARNESS/.venv-legacy"
RUN="$HARNESS/var/legacy-run"

if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" -q install -r "$HARNESS/requirements-legacy.txt"
fi

rm -rf "$RUN"; mkdir -p "$RUN/db"
"$VENV/bin/python" - "$ROOT/verification/replay/fixtures/seed.sql" "$RUN/db/ticketd.sqlite3" <<'EOF'
import sqlite3, sys
con = sqlite3.connect(sys.argv[2]); con.executescript(open(sys.argv[1]).read()); con.commit()
EOF

cd "$RUN"
PYTHONPATH="$ROOT/$LEGACY_DIR" nohup "$VENV/bin/python" "$HARNESS/legacy_boot.py" \
  --port "$PORT" --outbox "$RUN/outbox.jsonl" > "$RUN/server.log" 2>&1 &
echo $! > "$RUN/server.pid"

for i in $(seq 1 50); do
  if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/tickets"; then
    echo "legacy up on :$PORT (pid $(cat "$RUN/server.pid"))"; exit 0
  fi
  sleep 0.2
done
echo "legacy failed to boot — see $RUN/server.log" >&2; exit 1
