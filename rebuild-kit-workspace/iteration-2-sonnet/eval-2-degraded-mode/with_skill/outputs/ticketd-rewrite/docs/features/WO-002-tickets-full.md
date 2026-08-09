# WO-002 — Tickets: full behaviors (list, create, get)

id: WO-002            depends_on: [WO-001]              milestone: M1
risk: 0.45 (inferred-claim ratio low; complexity low-moderate; 2 open ASKs touch this area
  [invalid-priority error contract, OQ-005 slug uniqueness] neither of which blocks the WO but
  both flag gate review; no legacy test coverage)
usage_weight: 0.35 (static proxy — highest route-reference count of any feature area; list+get
  are the routes a UI would call most)
pain_weight: 0.05 (no PB entry targets this area directly; OQ-005's slug-collision proposal is
  the only pain-adjacent item, and it's unconfirmed)
context_budget: ~400 lines (this WO + docs/features/draft/tickets-list-create-get.md +
  docs/domain/ticket.md + relevant openapi.yaml paths)
gate: false

## Reading list

`docs/features/draft/tickets-list-create-get.md` (full behavior list, cited), `docs/domain/
ticket.md` (entity + invariants), `docs/contracts/openapi.yaml` paths `/api/tickets`,
`/api/tickets/{tid}`.

## Behaviors (see the draft spec for full citations — summarized here to the level this WO needs)

- statement: `GET /api/tickets` — optional exact-match `status` filter, `ORDER BY created_at
  DESC`, no pagination, bare JSON array response.
  fidelity: FIXED
- statement: `POST /api/tickets` — full priority coercion (`low/med/high` or `1/2/3`), title
  validation, slug derivation. See WO-001 for the subset already built; this WO completes it.
  fidelity: FIXED (coercion) / ASK — `docs/open-questions.md#OQ-008` (invalid-priority error
  contract) and `#OQ-009` (non-string title / explicit-null priority crash paths — P9 audit
  findings; note OQ-009's reading B: a Pydantic-based FastAPI implementation may reject these at
  the validation layer automatically, before ever reaching the "port the 500" question — read
  OQ-009 before assuming this is a free choice).
- statement: `GET /api/tickets/<id>` on missing ticket returns `200 {}`, not `404`. THE
  single most load-bearing FIXED behavior in this WO — the legacy comment itself asserts a
  caller dependency. `verification/characterization/test_tickets.py::
  test_get_missing_ticket_returns_200_empty_object` exists specifically to catch a regression
  here.
  fidelity: FIXED
- statement: slug uniqueness is NOT enforced today (collisions possible). Port as-is;
  `docs/open-questions.md#OQ-005` flags this for gate review, doesn't block this WO.
  fidelity: FIXED, flagged OQ-005

## Escalation

`legacy/app/server.py:27-64`, `legacy/app/util.py:1-7` only if citations are ambiguous.

## Acceptance

- L1: full `/api/tickets` + `/api/tickets/{tid}` GET validated against openapi.yaml.
- L2: `verification/characterization/test_tickets.py` full pass except close/export tests
  (WO-004/WO-005's territory).
- L3: `verification/harness/diff-run.sh tickets` — all `tickets-00*` through `tickets-013-*` and
  `tickets-017-*` traces pass (close-related traces 014-016 are WO-004's acceptance, not this
  WO's — but nothing stops you from getting a bonus green here too).
