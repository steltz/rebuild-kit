#!/usr/bin/env bash
# Boot legacy/ and record golden traces. Requires: python3 with Flask importable
# (pip install flask — legacy's own declared framework; not a modern/ dependency).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python3 "$ROOT/verification/harness/run_legacy.py"
