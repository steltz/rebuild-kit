# Fixtures

Golden payloads seeding characterization tests (P7). All are T3-tier (statically derived —
realistic hand-built examples, not captured production traffic; `rebuild.json.evidence`
records why no T1/T2-real corpus exists this run).

## Tickets

- `ticket-open.json` — a normal open ticket, all fields populated per schema.
- `ticket-closed.json` (id=2, title "Fix DB", slug "fix-db") — closed ticket, `closed_at` set.
- `ticket-slug-collision.json` (id=3, title "fix db!", slug "fix-db") — paired with
  `ticket-closed.json` to exercise the documented, unfixed slug-collision behavior
  (`docs/domain/ticket.md`, `legacy/app/util.py:5-6`). Both fixtures are independently schema-
  valid; the collision is in their `slug` values being equal despite distinct `title`s — a
  cross-fixture assertion for the characterization suite, not something the schema itself
  encodes.

All three validate against `../schemas/ticket.schema.json` (see `../../../verification/` for
the validation run).

## Auth/Reset

Not fixture files (the request/response bodies are trivial — see `docs/contracts/openapi.yaml`
inline examples via each schema). Reset-flow characterization tests instead drive the DB/token
state directly (rate-limit counters, expiry timestamps) since the interesting behavior is in
timing/state, not payload shape — see `verification/characterization/`.
