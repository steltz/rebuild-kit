id: WO-001            depends_on: []                     milestone: M0
risk: 0.55 (inferred-claim ratio low, but complexity: whole-stack decisions land here;
  legacy coverage: none; churn: n/a — new code) — gate: true because this WO's FREE choices
  (project layout, ORM/session pattern, error-handling shape) become the substrate every later
  WO builds on; a bad call here is expensive to unwind.
usage_weight: 0.829 (GET /api/tickets 0.6175 + POST /api/tickets 0.2115 — see usage-weights.json;
  LOW-MEDIUM CONFIDENCE, see usage-weights.json.notes on the access log's synthetic window)
pain_weight: 0.1 (neither PB-001/002/003 touches these two routes directly)
context_budget: ~400 lines (this WO + docs/00-overview.md + docs/domain/ticket.md +
  docs/contracts/openapi.yaml paths for /api/tickets + modern/CLAUDE.md)
gate: true

## What this WO does
Stand up the FastAPI + Postgres skeleton (project layout, DB connectivity, error-handling
convention, request/response model pattern) and implement the two highest-traffic routes:
`GET /api/tickets` and `POST /api/tickets`. This is Milestone 0 — the walking skeleton: it
validates the stack choice, proves the twin-boot harness plumbing end-to-end (both trees
booting, real diff), and surfaces systemic spec misreads while they cost one WO instead of
forty (P8 procedure). Nothing here depends on PB-001/002/003's REPAIRs — those are separable
(WO-002 onward) so M0 stays as thin as the "walking skeleton" framing demands.

behaviors:
  - statement: "GET /api/tickets returns every ticket row (all columns), ordered by created_at
      DESC, as a JSON array. Optional ?status=<value> exact-match filters; any string accepted,
      non-matching values return an empty array rather than erroring. No pagination."
    fidelity: FIXED
    evidence: [legacy/app/server.py:27-37, docs/features/draft/tickets-list.md]
    divergence: none
  - statement: "POST /api/tickets: title required (422 {error:title_required} if missing/
      empty/whitespace-only). priority accepts '1'/'2'/'3' OR low/med/high, defaults 'med' if
      omitted; any other value hits an uncaught DB CHECK violation today (500) -- reproduce
      as-is, do not silently harden into a 4xx (no PB entry sanctions that change). status
      always 'open' at creation. slug computed via slugify(title) -- NOT yet guaranteed
      unique, that's WO-005's job, blocked on OQ-001; WO-001 reproduces the CURRENT
      not-necessarily-unique behavior. Response 201 {id, slug}."
    fidelity: FIXED (including the 500-on-invalid-priority gap and the not-yet-unique slug)
    evidence: [legacy/app/server.py:40-55, docs/features/draft/tickets-create.md]
    divergence: none
  - statement: "Response field shapes/types match the legacy Ticket schema exactly (see
      docs/contracts/openapi.yaml#/components/schemas/Ticket), including assignee_id always
      null (nothing sets it) and naive-local-time-shaped created_at/closed_at strings pending
      OQ-003's ruling."
    fidelity: FIXED
    evidence: [legacy/db/schema.sql:1-10, docs/domain/ticket.md]
  - statement: "Project layout, ORM choice, session-management pattern, error-handling
      convention (HTTPException with legacy-matching detail bodies, not FastAPI's default
      validation envelope)."
    fidelity: FREE — outcome required (contract-equivalent responses); mechanism per
      modern/CLAUDE.md conventions. Record the actual choices made in ledger.json free_choices
      when this WO closes -- every later WO inherits them without re-litigating.

acceptance:
  replay_set: tickets-list-*.jsonl (4 traces), tickets-create-*.jsonl (8 traces) -- both
    already captured as T2 legacy goldens, verification/replay/traces/legacy/{tickets-list,
    tickets-create}.jsonl, self-check validated (0 unexpected diffs, see verification/harness/README.md)
  tests: verification/characterization/test_against_golden.py (parametrized; run with
    MODERN_BASE_URL pointed at this WO's boot)
  l1: docs/contracts/openapi.yaml paths /api/tickets (GET, POST) validate against implementation
  l3: verification/harness/diff-run.sh tickets-list && verification/harness/diff-run.sh tickets-create
    (run-modern.sh must be implemented as part of this WO -- see its header comment)

escalation: consult legacy/app/server.py:27-55 only if a specific field's shape is ambiguous
  after reading docs/contracts/openapi.yaml and docs/features/draft/tickets-{list,create}.md;
  do not bulk-read legacy/.

## Milestone-close note
M0 closing means: `verification/harness/run-modern.sh` is no longer a stub (its guard clause
in the generated version fails loudly on purpose -- replace it), both replay suites pass L3,
and `modern/CLAUDE.md`'s FREE choices are recorded. This is the gate the rest of the backlog
sits behind -- per root CLAUDE.md, STOP and get human sign-off before M1 starts (risk 0.55,
gate: true).
