# WO-001 — Walking skeleton (M0)

id: WO-001            depends_on: []                    milestone: M0
risk: 0.35 (inferred-claim ratio low — behaviors are directly cited; complexity low; no legacy
  test coverage to lean on; elevated slightly because it's the FIRST code and any systemic
  misread here propagates to every later WO)
usage_weight: 0.30 (static proxy — GET/POST /api/tickets are the two most-referenced routes in
  the legacy code and the only ones a client could plausibly call before anything else exists)
pain_weight: 0.0 (no PB entry targets this slice specifically — it exists to prove the stack,
  not to fix anything)
context_budget: ~250 lines (this WO + docs/domain/ticket.md + docs/contracts/openapi.yaml's
  /api/tickets paths)
gate: true (milestone-close gate — M0 always requires human sign-off per the executor loop
  before M1 starts; see root CLAUDE.md step 8)

## What this WO does

Stand up the FastAPI + PostgreSQL skeleton end to end: app boots, connects to Postgres, and
serves exactly two routes — enough of a real slice to prove the twin-boot harness plumbing works
against a real `modern/` before forty more work orders build on top of an unproven foundation.
This is the M0 walking skeleton the skill's P8 procedure requires: "entry, one core action,
persistence, response."

## Behaviors (subset of docs/features/draft/tickets-list-create-get.md — read that file for the
## full Tickets spec; WO-002 covers the rest)

- statement: `POST /api/tickets` accepts `{title, priority?}`. `title` required, server-stripped,
  blank-after-strip is `422 {"error": "title_required"}`. Success is `201 {"id", "slug"}`.
  fidelity: FIXED
  evidence: [legacy/app/server.py:41-55]
- statement: `GET /api/tickets/<id>` returns `200` with the full ticket if found. (The
  `200`-with-`{}`-on-missing quirk is FIXED too but deferred to WO-002 for the initial skeleton —
  the happy path is enough to prove the stack; do not skip it when WO-002 lands.)
  fidelity: FIXED
  evidence: [legacy/app/server.py:58-64]
- statement: `priority` defaults to `med`; storage/query mechanism (SQLAlchemy vs. raw SQL) is
  FREE — see `modern/CLAUDE.md`. Record the choice made in `ledger.json` notes; every later WO
  touching `tickets` inherits it.
  fidelity: FREE
  evidence: n/a — mechanism choice, not a legacy behavior claim

## Escalation

Consult `legacy/app/server.py:1-55` only if this WO's citations are ambiguous. Do not read past
line 55 — that's WO-002/WO-003/WO-004 territory.

## Acceptance

- L1: request/response validate against `docs/contracts/openapi.yaml` (`/api/tickets` GET+POST,
  `/api/tickets/{tid}` GET only, for this WO's subset).
- L2: a minimal subset of `verification/characterization/test_tickets.py` —
  `test_create_requires_title`, `test_create_default_priority_is_med` — passes against `modern/`.
  (Running the FULL file now is fine and encouraged; the rest just won't be relevant until
  WO-002/WO-004 land their behaviors — a failure in an out-of-scope test isn't this WO's problem,
  but a pass is a nice bonus signal.)
- L3: `verification/harness/diff-run.sh tickets` — full pass is WO-002's bar, not this WO's; for
  M0, the bar is narrower: booting `verification/harness/run-modern.sh` successfully at all (it
  currently exits 2 — implementing it, even partially, is this WO's deliverable alongside the
  app itself) and getting `tickets-001-list-initial`, `tickets-005-create-numeric-priority`,
  `tickets-010-get-created` to pass individually.
- Gate: STOP after L1/L2/M0-subset-L3 pass. Emit the gate packet (`templates/gate-packet.md`) to
  `guide/briefs/`. A human must approve before M1 starts — this is the point where the stack
  choice and harness plumbing get real scrutiny while the cost of being wrong is still one WO.
