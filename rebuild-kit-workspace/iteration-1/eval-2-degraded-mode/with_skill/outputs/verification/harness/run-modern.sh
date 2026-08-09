#!/usr/bin/env bash
# Boot the modern tree for a harness run — delegates to the boot entrypoint the executor
# provides at modern/harness/boot.sh (WO-001 acceptance includes making this work).
#
# Contract boot.sh must satisfy (see README.md for full details):
#   inputs : PORT, HARNESS=1, SEED_JSON (abs path to harness/seed.json)
#   effects: app serving on PORT against a FRESH database loaded from SEED_JSON;
#            under HARNESS=1 exposes GET /__harness__/state and GET /__harness__/emails
#   stdout : MODERN_BASE_URL=... , MODERN_PIDS=... (space-separated pids to kill)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
MODERN_DIR="$ROOT/$(python3 -c "import json;print(json.load(open('$ROOT/rebuild.json'))['layout']['modern_dir'])")"
BOOT="$MODERN_DIR/harness/boot.sh"
if [ ! -x "$BOOT" ]; then
  echo "run-modern.sh: $BOOT not found or not executable." >&2
  echo "The modern app must provide it (WO-001). See verification/harness/README.md." >&2
  exit 2
fi
PORT="${PORT:-5002}" HARNESS=1 SEED_JSON="$HERE/seed.json" exec "$BOOT"
