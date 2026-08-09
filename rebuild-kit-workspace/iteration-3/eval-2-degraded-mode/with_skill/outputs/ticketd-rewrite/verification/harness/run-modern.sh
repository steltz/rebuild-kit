#!/usr/bin/env bash
# Boot modern/ and record traces for diffing. Requires: fastapi[testclient] once modern/
# exists; harmless (prints a clear "not implemented" status) before then.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
python3 "$ROOT/verification/harness/run_modern.py"
