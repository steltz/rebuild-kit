#!/usr/bin/env bash
# Boots the modern/ (FastAPI) app the same way run-legacy.sh boots legacy: fresh Postgres (or
# whatever WO-001 lands, see modern/CLAUDE.md) seeded from a translated version of
# verification/replay/corpus/seed.sql (see docs/migration/mapping.md once it exists), one
# instance per suite for hermetic replay.
#
# THIS SCRIPT IS A CONTRACT, NOT YET AN IMPLEMENTATION: modern/ is an empty tree at generation
# time (P0-P10 ran before any work order was implemented -- see SKILL.md "you generate, you
# never rewrite"). It fails loudly and immediately below until the executor's first work order
# (WO-001, "walking skeleton") gives it something real to boot. Replace the body below with the
# actual modern-app boot sequence when WO-001 closes; keep the interface
# (suite-name, port -> prints db connection info on stdout, ready-check on the same routes)
# identical so diff-run.sh does not need to change.
#
# Usage: run-modern.sh <suite-name> <port>
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SUITE="${1:?usage: run-modern.sh <suite-name> <port>}"
PORT="${2:?usage: run-modern.sh <suite-name> <port>}"

if [ ! -f "$ROOT/modern/CLAUDE.md" ] || [ -z "$(find "$ROOT/modern" -mindepth 1 -not -name CLAUDE.md 2>/dev/null)" ]; then
  cat >&2 <<'EOF'
run-modern.sh: modern/ has no application code yet beyond CLAUDE.md.
This is expected before Milestone 0 closes -- see backlog.md and root CLAUDE.md's executor
loop. Once WO-001 (walking skeleton) exists, implement this script's boot sequence (start
FastAPI + Postgres/whatever WO-001 chose, apply the seed, wait for readiness on the same
routes legacy serves) and delete this guard clause. Until then diff-run.sh cannot run L3 --
use L1 (contract validation) and L2 (characterization tests) only.
EOF
  exit 2
fi

echo "TODO: implement modern boot sequence (see comment header). Suite=$SUITE Port=$PORT" >&2
exit 2
