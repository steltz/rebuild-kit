#!/bin/sh
# Twin-boot: legacy side. Boots ticketd/ (READ-ONLY) from a scratch COPY -- never writes into
# ticketd/ itself. Validated during P7 generation: this exact procedure produced the traces under
# verification/replay/traces/. Requires: python3 with `flask` installed (a venv is fine; nothing
# in this script assumes a specific interpreter beyond $PYTHON), sqlite3 CLI.
#
# Usage: verification/harness/run-legacy.sh [port]   (default port 5099)
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${1:-5099}"
SCRATCH="$(mktemp -d /tmp/ticketd-legacy-boot.XXXXXX)"
PYTHON="${PYTHON:-python3}"

cleanup() { rm -rf "$SCRATCH"; }
trap cleanup EXIT

# Copy (never symlink -- symlinking risks an accidental write reaching the read-only pin) app +
# schema out of the legacy dir into a writable scratch dir.
cp -R "$ROOT/ticketd/app" "$SCRATCH/app"
mkdir -p "$SCRATCH/db"
cp "$ROOT/ticketd/db/schema.sql" "$SCRATCH/db/schema.sql"
chmod -R u+w "$SCRATCH"

sqlite3 "$SCRATCH/db/ticketd.sqlite3" < "$SCRATCH/db/schema.sql"

cp "$ROOT/verification/harness/fake_smtp.py" "$SCRATCH/fake_smtp.py"
cat > "$SCRATCH/boot.py" <<'EOF'
import fake_smtp  # noqa: F401 -- must patch smtplib before app.server imports app.notify
from app.server import app

if __name__ == "__main__":
    import os
    app.run(port=int(os.environ.get("TICKETD_PORT", "5099")))
EOF

echo "legacy scratch boot dir: $SCRATCH" >&2
echo "sent-mail log: ${TICKETD_FAKE_SMTP_LOG:-/tmp/ticketd_harness_sent_mail.jsonl}" >&2
cd "$SCRATCH"
TICKETD_PORT="$PORT" "$PYTHON" boot.py
# NOTE: trap cleanup runs on exit, including Ctrl-C -- the scratch dir (and its sqlite file) does
# not persist across runs by design. If a WO's replay set needs seeded rows beyond the schema,
# add an INSERT step here reading from a fixture under docs/contracts/fixtures/, not by hand-editing
# this script per run.
