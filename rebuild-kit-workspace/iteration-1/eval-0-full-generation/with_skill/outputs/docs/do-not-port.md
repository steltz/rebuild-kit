# Do Not Port — negative space (binding on the executor)

Each entry: what it is, the evidence it is dead or unwanted, and its sanction. The executor
never rebuilds anything listed here; if an entry turns out to be needed, that discovery is an
open-questions.md filing, not a silent re-add.

## DNP-001 — `GET /internal/export/csv` (pending human ratification, OQ-003)
- what: CSV dump of all tickets, `ticketd/app/server.py:111-115`
- evidence dead: source comment "written for the 2020 audit; no caller since"
  (`ticketd/app/server.py:112`); zero traffic in the 30-day window (`zero-traffic.md`)
- caveat: annual-audit cadence is invisible to a 30-day window → **ruling required**
  (OQ-003) before cutover; until ruled, it is simply not scheduled in any WO
- also note: its CSV assembly is injection-unsafe (no quoting of commas/newlines in
  titles, `ticketd/app/server.py:114`) — if a "keep" ruling arrives, that becomes a
  REPAIR-vs-bug-for-bug decision inside the new WO

## DNP-002 — `app/legacy_import.py` (spreadsheet importer)
- what: one-off CSV importer from the 2019 spreadsheet migration,
  `ticketd/app/legacy_import.py:1-8`
- evidence dead: its own docstring — "Nothing imports this module"
  (`ticketd/app/legacy_import.py:1`) — corroborated by the P1 dependency graph
  (zero inbound edges) and no route references
- sanction: dead-code removal is not a behavior change; no ruling needed

## DNP-003 — Unbounded accumulation of expired reset tokens
- what: expired tokens are never deleted — deletion happens only on successful confirm
  (`ticketd/app/server.py:106`); expired rows sit in `reset_tokens` forever
- evidence: no purge path anywhere in the app; bare table with no TTL
  (`ticketd/db/schema.sql:18-22`)
- sanction: PB-002 (REPAIR of token storage) covers this — the modern store expires rows;
  the *accumulation* behavior itself must not be ported. Migration note: existing
  `reset_tokens` rows are all ≤30-minute artifacts and are **not migrated** (see
  `docs/migration/mapping.md`, ratification tracked there).

## DNP-004 — Dead code fragments in `app/server.py`
- what: unused imports `hashlib`-adjacent `smtplib`, `time` usage aside — specifically
  `import smtplib` at `ticketd/app/server.py:4` (never used in the module; mailing goes
  through `app/notify.py`), and the trailing no-op comment block "tweak 1..3"
  (`ticketd/app/server.py:120-125`, hotfix residue)
- sanction: dead-code removal, no behavior change, no ruling needed
