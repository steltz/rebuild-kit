#!/bin/sh
# Twin-boot: modern side. PLACEHOLDER -- modern/ is an empty tree as of this generator run (P0-P10
# scaffold the workspace; implementation is the executor's job, not this generator's). This script
# documents the contract the executor must fulfill, and will fail loudly until it does, rather
# than silently no-op.
#
# Usage: verification/harness/run-modern.sh [port]   (default port 5100 -- distinct from
# run-legacy.sh's 5099 so both can run simultaneously for diff-run.sh)
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${1:-5100}"

if [ ! -f "$ROOT/modern/pyproject.toml" ] && [ ! -f "$ROOT/modern/requirements.txt" ]; then
  echo "run-modern.sh: modern/ has no pyproject.toml or requirements.txt yet." >&2
  echo "This is expected before M0/WO-000 lands application code. Once it does, replace this" >&2
  echo "script's body with the real boot sequence: install deps (in a venv, never system-wide)," >&2
  echo "run Alembic migrations against a scratch Postgres instance (see docs/contracts/ddl.sql +" >&2
  echo "docs/migration/mapping.md for the target schema), start uvicorn on \$PORT, and stub the" >&2
  echo "notification dispatch mechanism the same way run-legacy.sh stubs SMTP (see fake_smtp.py --" >&2
  echo "modern's stub covers whatever WO-001 actually builds: BackgroundTasks, a queue client, etc." >&2
  echo "-- it does not need to match fake_smtp.py's shape, only its intent: no real external call)." >&2
  exit 1
fi

echo "run-modern.sh: modern/ has dependency manifests but this script has not been filled in yet." >&2
echo "Update this script as part of the WO that first makes modern/ runnable (expected: WO-000/M0)." >&2
exit 1
