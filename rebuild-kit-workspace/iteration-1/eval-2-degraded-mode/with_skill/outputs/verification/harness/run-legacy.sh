#!/usr/bin/env bash
# Boot the pinned legacy tree for a harness run. Emits env lines for the driver.
# Env overrides: PORT (5001), SMTP_STUB_PORT (51025), RUNDIR (fresh temp), VENV (cached).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
LEGACY_DIR="$ROOT/$(python3 -c "import json;print(json.load(open('$ROOT/rebuild.json'))['layout']['legacy_dir'])")"
PORT="${PORT:-5001}"
SMTP_STUB_PORT="${SMTP_STUB_PORT:-51025}"
RUNDIR="${RUNDIR:-$(mktemp -d /tmp/ticketd-legacy-run.XXXXXX)}"
VENV="${VENV:-$RUNDIR/venv}"

# refuse to run against a stale instance — a previous boot still owning the port would
# silently serve the wrong DB/stub and corrupt traces
if curl -sf "http://127.0.0.1:$PORT/api/tickets" >/dev/null 2>&1; then
  echo "run-legacy.sh: something already serving on port $PORT — kill it first" >&2
  exit 1
fi

if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
  "$VENV/bin/pip" -q install "flask>=2,<4"
fi

python3 "$HERE/seed.py" --rundir "$RUNDIR" >&2
# NB: background children must NOT inherit stdout — callers use $(run-legacy.sh) and the
# command substitution would wait for their EOF.
python3 "$HERE/smtp_stub.py" --port "$SMTP_STUB_PORT" --log "$RUNDIR/smtp-log.jsonl" \
  >"$RUNDIR/smtp-stub.log" 2>&1 &
STUB_PID=$!
LEGACY_DIR="$LEGACY_DIR" RUNDIR="$RUNDIR" PORT="$PORT" SMTP_STUB_PORT="$SMTP_STUB_PORT" \
  "$VENV/bin/python" "$HERE/legacy_boot.py" >"$RUNDIR/legacy.log" 2>&1 &
APP_PID=$!

for i in $(seq 1 50); do
  if curl -sf "http://127.0.0.1:$PORT/api/tickets" >/dev/null 2>&1; then break; fi
  sleep 0.2
done
curl -sf "http://127.0.0.1:$PORT/api/tickets" >/dev/null || {
  echo "legacy failed to boot; see $RUNDIR/legacy.log" >&2; kill "$STUB_PID" "$APP_PID" 2>/dev/null || true; exit 1; }

echo "LEGACY_BASE_URL=http://127.0.0.1:$PORT"
echo "LEGACY_DB=$RUNDIR/db/ticketd.sqlite3"
echo "LEGACY_SMTP_LOG=$RUNDIR/smtp-log.jsonl"
echo "LEGACY_PIDS='$APP_PID $STUB_PID'"
echo "LEGACY_RUNDIR=$RUNDIR"
