# scripts/

Copied from the rebuild-kit skill (`references/…/scripts/`, skill_version 1.0 — see
`rebuild.json.skill_version`) at generation time, so this root is self-contained: the executor
opens this directory with **no skill installed** (per the root CLAUDE.md contract) and still
needs `replay.py` for L3 verification, `render_guide.py` for guide regeneration on milestone
close, `staleness_check.py` to re-verify citations if legacy ever needs re-pinning, and
`inventory.py`/`census.py`/`evidence.py` if a spec-patch re-run needs them. `scaffold.py` is
intentionally NOT copied — it's P0/generator-only and asserts `rebuild.json` doesn't already
exist, which would never be true here.

`validate_fixtures.py` is local to this workspace (not from the skill) — a small ad hoc P5
helper that validates `docs/contracts/fixtures/*.json` against `docs/contracts/openapi.yaml`'s
component schemas. Re-run it if fixtures change: `python3 scripts/validate_fixtures.py`.

Stdlib only, no pip dependencies — matches the skill's own design constraint.
