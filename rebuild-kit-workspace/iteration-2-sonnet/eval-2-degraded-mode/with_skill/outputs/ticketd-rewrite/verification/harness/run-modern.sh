#!/bin/sh
# Twin-boot: modern side. NOT YET IMPLEMENTABLE — modern/ is empty until M0 lands (this is
# expected: P7 builds the harness before any modern code exists, per the skill's playbook,
# so the harness is ready on day one of execution rather than bolted on after the fact).
#
# Once modern/ has a FastAPI app (per modern/CLAUDE.md), this script should:
#   1. stand up a scratch Postgres (docker or local), apply the target schema
#      (docs/migration/mapping.md once ratified; not docs/contracts/ddl.sql, which is the
#      LEGACY/current schema, frozen verbatim on purpose),
#   2. seed it with the same logical fixtures as verification/harness/seed.sql (translated to
#      the target schema),
#   3. run `uvicorn app.main:app --port <port>` (or whatever modern/CLAUDE.md's layout says),
#   4. emit traces via verification/harness/capture_traces.py exactly as run-legacy.sh does,
#      so diff-run.sh can compare them apples-to-apples.
set -e
echo "run-modern.sh: modern/ has no application yet (pre-M0). Implement this script as part of" >&2
echo "M0 (the walking skeleton) — see backlog.md and docs/features/WO-001.md." >&2
exit 2
