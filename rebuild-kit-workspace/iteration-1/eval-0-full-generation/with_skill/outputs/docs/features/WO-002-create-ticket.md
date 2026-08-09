# WO-002 — Create ticket

id: WO-002            depends_on: [WO-001]          milestone: M1
risk: 0.55 (2 open ASKs touch it — OQ-001 slug target, OQ-007 invalid-priority; PB-003 medium; claims cited+traced)
usage_weight: 0.2115  pain_weight: 0.12             context_budget: ~350 lines   gate: true

Reading list: this file · `docs/contracts/openapi.yaml` (POST /api/tickets) ·
`docs/features/draft/tickets-create.md` · `docs/open-questions.md#OQ-001` `#OQ-007`.

behaviors:
  - statement: Body JSON; non-JSON/absent body tolerated as {} (silent parse) — a missing
      title then 422s; malformed JSON NEVER returns a 400 parse error.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:42, trace: t2-core#tickets-create-011]
  - statement: title required after strip; missing/blank → 422 {"error":"title_required"};
      stored title is the stripped string.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:43-45,52, traces: tickets-create-001/004/005]
  - statement: priority accepted as int or string; "1"/"2"/"3" (post-str() coercion) map to
      low/med/high; absent → "med"; "low"/"med"/"high" pass through. Both client styles must
      keep working.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:46-49, traces: tickets-create-002/003/009]
  - statement: any OTHER priority value currently passes through raw and 500s on the DB CHECK
      (text/html error page).
    fidelity: ASK — open-questions.md#OQ-007 (blocks: none; flags this gate). Until ruled:
      preserve a 500-class response for such input (any 5xx + text/html is acceptable;
      trace ask-priority-500 stays OUT of acceptance).
    evidence: [ticketd/app/server.py:47-49, ticketd/db/schema.sql:5, trace: t2-edge-ask#ask-priority-500]
  - statement: slug = slugify(title) — lowercase, non-alphanumerics collapsed to "-",
      strip "-", truncate 64; collisions allowed (no unique constraint).
    fidelity: REPAIR (PB-003) — target behavior PENDING ruling OQ-001; implement EXACT
      legacy behavior until the ruling lands (no divergence entry exists yet — replay
      enforces byte-equality on slugs).
    evidence: [ticketd/app/util.py:4-6, ticketd/db/schema.sql:4, traces: tickets-create-006/007/008]
  - statement: unknown body fields silently ignored; assignee_id not settable via API.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:42-52, trace: tickets-create-010]
  - statement: response 201 {"id": <int>, "slug": "<slug>"} (prod log shows 200 — OQ-009;
      the pinned boot's 201 is authoritative).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:55, trace: tickets-create-001]
  - statement: created_at stamping mechanism.
    fidelity: FREE — rationale: DB-side now() vs app clock is mechanism; L3 normalizes
      timestamps. Format/TZ policy inherits OQ-005's ruling for migration parity.

acceptance:
  replay_set: tickets-create-001..011 from t2-core (11 traces; no divergences apply)
  tests: verification/characterization/test_tickets.py — create/slug tests (CHAR_TARGET=modern)
gate_packet_note: gate review should surface OQ-001 and OQ-007 for ruling — both are
  cheap to rule now and expensive after M1 closes.
escalation: consult ticketd/app/server.py:40-55, ticketd/app/util.py:4-6 only on ambiguity.
