id: WO-000            depends_on: []                    milestone: M0
risk: 0.35 (inferred-claim ratio low, ASK density none, no PB defect directly, first-of-its-kind
  infra risk offset by small scope)
usage_weight: n/a (infrastructure)   pain_weight: n/a   context_budget: ~250 lines   gate: true

## Why this WO exists

Milestone 0 is always the walking skeleton (P8 design rule): the thinnest possible end-to-end
slice that proves the stack choice, the twin-boot harness, and contract fidelity before forty more
work orders build on unverified plumbing. ticketd has no auth/session layer to slice through (see
`docs/open-questions.md#OQ-007`), so the skeleton's "one core action" is `GET /api/tickets` — the
single highest-traffic route in the whole system (61.75% of sampled requests,
`usage-weights.json`), a pure read with zero side effects, the simplest possible thing that still
exercises real Postgres persistence and a real JSON response shape.

## Reading list (context budget: read only these)

- `modern/CLAUDE.md` — target stack, conventions.
- `docs/contracts/openapi.yaml` (path `/api/tickets` GET only) + `docs/contracts/schemas/ticket.json`.
- `docs/contracts/ddl.sql` (legacy DDL, for the `tickets` table shape) + `docs/migration/mapping.md`
  (table: tickets) for the target Postgres types.
- `verification/replay/traces/tickets-crud.jsonl`, trace id `tickets-list-empty-001` and
  `tickets-list-filter-open-010` / `tickets-list-filter-bogus-011`.
- `verification/harness/run-legacy.sh`, `run-modern.sh`, `diff-run.sh` — you will fill in
  `run-modern.sh`'s placeholder as part of this WO.

## Behaviors

- statement: A FastAPI application boots, connects to Postgres (via whatever ORM/driver WO chose
    is FREE — SQLAlchemy async or asyncpg direct, `modern/CLAUDE.md`), and Alembic migrations
    create at least the `tickets` table per `docs/contracts/ddl.sql` + `docs/migration/mapping.md`'s
    target-type column (note: `assignee_id`'s FK-orphan handling and `created_at`/`closed_at`'s
    timezone representation are still open — OQ-006/OQ-009/mapping.md's orphaned-FK policy — but
    the `tickets` table DDL itself, minus those two specific column-type decisions, is not blocked;
    use `TIMESTAMP` (naive) as the interim default for `created_at`/`closed_at` per OQ-006's
    "default to FIXED" guidance, revisit if that OQ is ruled before this WO closes).
  fidelity: FREE (infrastructure choice; outcome required: the app boots and persists).
- statement: `GET /api/tickets` (no query param) returns `200` with a JSON array of all rows,
    ordered by `created_at DESC`, each object matching `docs/contracts/schemas/ticket.json`.
  fidelity: FIXED.
    evidence: [ticketd/app/server.py:27-37, trace: tickets-list-empty-001 in
    verification/replay/traces/tickets-crud.jsonl]
- statement: `GET /api/tickets?status=open` (or `closed`) filters to exact match; any other
    NON-EMPTY value (including nonsense strings) returns an empty array, not an error. **Correction
    (P9 audit finding, PB-011/OQ-011)**: this does NOT hold for the empty string specifically —
    `?status=` (empty value) is falsy in `if status:` (`server.py:32`) and is treated as if the
    param were absent, returning the FULL unfiltered list, not an empty array. The original phrasing
    here ("any other value... returns an empty array") was too broad; verified but not yet traced,
    see `docs/open-questions.md#OQ-011` and WO-002's fuller writeup of this same correction.
  fidelity: FIXED.
    evidence: [ticketd/app/server.py:29-34, traces: tickets-list-filter-open-010,
    tickets-list-filter-bogus-011]
- statement: No pagination — full result set every time, regardless of row count.
  fidelity: FIXED — required by PB-006 (no UI changes; the UI depends on unpaginated results,
    `ticketd/app/server.py:35`). Do not add pagination even though it would be more idiomatic for a
    fresh FastAPI service — see `docs/domain/tickets.md`'s note on this being a real future scale
    risk that is explicitly out of scope for this rewrite.
- statement: `verification/harness/run-modern.sh` boots this application (fill in its placeholder
    body) on a distinct port from `run-legacy.sh`, against a scratch/test Postgres instance (not
    a shared dev DB), with migrations applied fresh each run for reproducibility.
  fidelity: FREE (harness mechanics), but REQUIRED for this WO's acceptance — `diff-run.sh` must
    successfully drive `tickets-crud.jsonl`'s list-only traces through it.

## Acceptance

- L1: `docs/contracts/openapi.yaml`'s `/api/tickets` GET operation validates against the live
  response shape (any OpenAPI validator; FastAPI's own generated schema is a reasonable substitute
  if it's kept in sync, but validate against the frozen contract file, not just self-consistency).
- L2: a live-modern equivalent of `verification/characterization/test_tickets_crud.py`'s
  `test_list_empty_is_array`, `test_list_filter_by_status`,
  `test_list_filter_bogus_status_returns_empty_not_error` — same assertions, driven against the
  running modern app instead of the frozen legacy trace.
- L3: `verification/harness/diff-run.sh tickets-crud` — this WO only needs the 3 list-related
  traces (`tickets-list-empty-001`, `tickets-list-filter-open-010`,
  `tickets-list-filter-bogus-011`) to pass; the other 10 traces in that file belong to WO-002 and
  are expected to fail/be absent until WO-002 lands (the `create`/`get` routes don't exist yet
  after this WO alone) — do not treat that as this WO's failure.
- gate: **true, always, per the walking-skeleton design rule** — this is the first thing built in
  `modern/`; a human must review it before anything else builds on top. Emit the gate packet per
  root `CLAUDE.md` step 7.

## Escalation

Consult `ticketd/app/server.py:1-37` only if the OpenAPI/schema/trace evidence above is ambiguous
about list behavior specifically — do not read the rest of the file for this WO; that's WO-001
through WO-005's job.
