#!/usr/bin/env bash
# Boots the modern/ (FastAPI + Postgres) app for real: fresh Postgres cluster, alembic
# migrations, the T2 seed fixture, then uvicorn -- one instance per suite for hermetic replay,
# mirroring run-legacy.sh's contract exactly (suite-name, port -> readiness check on the same
# routes, ONLY machine-readable output on stdout).
#
# WO-001 (walking skeleton) FREE choices this script encodes (see modern/CLAUDE.md, recorded
# in ledger.json): SQLAlchemy 2.x + psycopg3, Alembic migrations, a Python seed script
# (scripts/seed_db.py) rather than a hand-written SQL fixture, so seed row shape can't drift
# from app/models.py.
#
# Requires (see README.md): Postgres server+client binaries on PATH (initdb, pg_ctl, createdb,
# psql -- Homebrew's `postgresql@16` provides all four); modern/.venv with modern/requirements.txt
# installed (`python3 -m venv modern/.venv && modern/.venv/bin/pip install -r modern/requirements.txt`).
#
# stdout: the app's DATABASE_URL (postgresql+psycopg://...) -- the ONLY machine-readable line;
# drive_inputs.py's dump_db() uses this to connect (via psql) for state.db_dump.
#
# Usage: run-modern.sh <suite-name> <port>
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SUITE="${1:?usage: run-modern.sh <suite-name> <port>}"
PORT="${2:?usage: run-modern.sh <suite-name> <port>}"
PG_PORT=$((PORT + 10000))

MODERN_DIR="$ROOT/modern"
VENV="$MODERN_DIR/.venv"
RUN_DIR="$ROOT/verification/harness/.run/modern-$SUITE"
PGDATA_DIR="$RUN_DIR/pgdata"
PG_LOG="$ROOT/verification/harness/.run/modern-$SUITE-pg.log"
BOOT_LOG="$ROOT/verification/harness/.run/modern-$SUITE-boot.log"
PID_FILE="$ROOT/verification/harness/.run/modern-$SUITE.pid"
PGDATA_MARKER="$ROOT/verification/harness/.run/modern-$SUITE.pgdata"
DB_NAME="ticketd_$(echo "$SUITE" | tr -c 'a-zA-Z0-9' '_')"
DATABASE_URL="postgresql+psycopg://ticketd@127.0.0.1:${PG_PORT}/${DB_NAME}"

if [ ! -f "$VENV/bin/python" ]; then
  cat >&2 <<EOF
run-modern.sh: $VENV not found. Set up modern/'s virtualenv first:
  python3 -m venv modern/.venv && modern/.venv/bin/pip install -r modern/requirements.txt
EOF
  exit 2
fi

rm -rf "$RUN_DIR"
mkdir -p "$RUN_DIR"
: > "$BOOT_LOG"

echo "[run-modern] initdb -> $PGDATA_DIR" >> "$BOOT_LOG"
initdb -D "$PGDATA_DIR" -U ticketd -A trust --no-locale --encoding=UTF8 >> "$BOOT_LOG" 2>&1

echo "[run-modern] starting postgres on 127.0.0.1:$PG_PORT" >> "$BOOT_LOG"
pg_ctl -D "$PGDATA_DIR" -l "$PG_LOG" \
  -o "-p $PG_PORT -k $RUN_DIR -c listen_addresses=127.0.0.1" start >> "$BOOT_LOG" 2>&1
echo "$PGDATA_DIR" > "$PGDATA_MARKER"

for _ in $(seq 1 30); do
  pg_isready -h 127.0.0.1 -p "$PG_PORT" -U ticketd >/dev/null 2>&1 && break
  sleep 0.2
done

createdb -h 127.0.0.1 -p "$PG_PORT" -U ticketd "$DB_NAME" >> "$BOOT_LOG" 2>&1

echo "[run-modern] alembic upgrade head" >> "$BOOT_LOG"
(cd "$MODERN_DIR" && DATABASE_URL="$DATABASE_URL" "$VENV/bin/alembic" upgrade head) >> "$BOOT_LOG" 2>&1

echo "[run-modern] seeding" >> "$BOOT_LOG"
(cd "$MODERN_DIR" && DATABASE_URL="$DATABASE_URL" PYTHONPATH="$MODERN_DIR" "$VENV/bin/python" scripts/seed_db.py) >> "$BOOT_LOG" 2>&1

echo "[run-modern] starting uvicorn on :$PORT" >> "$BOOT_LOG"
# `exec` inside the subshell replaces the subshell's process image with uvicorn's, so $!
# (captured on the next line) is uvicorn's real PID -- without it, $! is the subshell's PID,
# uvicorn runs as its orphaned child, and stop.sh's `kill "$(cat "$PID_FILE")"` kills nothing.
(cd "$MODERN_DIR" && DATABASE_URL="$DATABASE_URL" PYTHONPATH="$MODERN_DIR" \
  exec "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$PORT" --log-level warning) \
  >> "$BOOT_LOG" 2>&1 &
echo $! > "$PID_FILE"

for _ in $(seq 1 30); do
  if curl -s -o /dev/null "http://127.0.0.1:$PORT/api/tickets"; then
    echo "modern [$SUITE] up on :$PORT (pid $(cat "$PID_FILE")), db=$DATABASE_URL" >&2
    echo "$DATABASE_URL"   # ONLY machine-readable output on stdout
    exit 0
  fi
  sleep 0.3
done
echo "modern [$SUITE] failed to boot -- see $BOOT_LOG" >&2
cat "$BOOT_LOG" >&2
exit 1
