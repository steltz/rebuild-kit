# Open Questions — ASK register & PB proposals

<!-- Executor + generator both append here. Never delete entries; rulings are appended.
     Each OQ with execution impact has a ruling brief in guide/briefs/. The team was not
     available during generation (non-interactive run), so several intake questions from
     docs/problem-brief.md are registered here. -->

## OQ-001 — What is the slug-collision fix? (PB-003)
- raised_by: generator P0 (intake) — "nobody has decided yet what the fix should be"
- kind: ambiguity (sanctioned problem, unratified target)
- readings / options:
  - A: unique index + numeric suffix on collision (`fix-db`, `fix-db-2`) — evidence of
    collision: `ticketd/app/util.py:5` comment, no constraint at `ticketd/db/schema.sql:4`
  - B: append short random suffix always (stable, never collides, changes every slug)
  - C: keep collisions (slug is display-only?) — no code reads `slug` back
    (`grep slug ticketd/app` shows write-only), so collisions may be harmless to the API
- blocks: []   (WO-002 implements legacy behavior verbatim until ruled; its gate review
  flags this — ruling before M1 avoids rework)
- ruling brief: `guide/briefs/OQ-001-ruling-brief.md`
- ruling: PENDING

## OQ-002 — `X-Internal-Bypass: 1` rate-limit bypass: keep or drop?
- raised_by: generator P4
- kind: ambiguity
- readings:
  - A: deliberate operational escape hatch for internal tooling — evidence: explicit header
    check `ticketd/app/server.py:84` ("undocumented bypass header")
  - B: forgotten debug hook that defeats the rate limit for anyone who learns the header —
    evidence: no doc, no auth around it, security-sensitive area (PB-002 adjacent)
- blocks: []   (WO-005 freezes current behavior via replay trace `auth-reset-req-005`;
  flags WO-005 gate review)
- ruling brief: `guide/briefs/OQ-002-ruling-brief.md`
- ruling: PENDING

## OQ-003 — Ratify dropping `GET /internal/export/csv` (do-not-port DNP-001)
- raised_by: generator P2 (zero-traffic report)
- kind: pb-proposal (drop a legacy behavior)
- readings:
  - A: dead since the 2020 audit — evidence: `ticketd/app/server.py:112` comment + zero
    traffic in the 30-day window (`zero-traffic.md`)
  - B: annual-audit tool that a 30-day window cannot observe — evidence: "written for the
    2020 audit" implies yearly cadence
- blocks: []   (not scheduled in any WO; if ruled "keep", a new WO is cut via spec-patch.
  Note: its CSV assembly does not escape commas/newlines in titles —
  `ticketd/app/server.py:114` — so a "keep" ruling should decide bug-for-bug vs REPAIR.)
- ruling brief: `guide/briefs/OQ-003-ruling-brief.md`
- ruling: PENDING

## OQ-004 — Email dispatch mechanism for the PB-001 repair
- raised_by: generator P0 (intake gap)
- kind: ambiguity (outcome ratified, mechanism preference unknown)
- readings / options:
  - A: Postgres transactional outbox + worker process (no new infra; atomic with the
    triggering write) — **generator default if unruled**
  - B: existing team queue infra (Redis/RabbitMQ/etc.) — unknown whether any exists
  - C: FastAPI BackgroundTasks (in-process; loses mail on crash — weakest)
- blocks: []   (WO-004 proceeds with option A as a FREE mechanism choice recorded in the
  ledger; a later ruling can redirect via spec-patch)
- ruling brief: `guide/briefs/OQ-004-ruling-brief.md`
- ruling: PENDING

## OQ-005 — Timezone/format policy for datetime migration
- raised_by: generator P6
- kind: ambiguity (data-mapping policy needs human ratification)
- readings:
  - A: legacy stores naive local-time ISO strings — evidence: `ticketd/app/server.py:52`
    (comment "naive local time!"), `datetime.now().isoformat()` also at :71; server TZ unknown
  - B: `reset_tokens.created_ts` is epoch UTC (`time.time()`, `ticketd/app/server.py:92`) —
    the two tables disagree about time representation
- question: what TZ has prod been running in, and should Postgres store `timestamptz` UTC
  (converting historical values during migration)?
- blocks: [WO-007]   (mapping policy for `created_at`/`closed_at` is ASK until ratified)
- ruling brief: `guide/briefs/OQ-005-ruling-brief.md`
- ruling: PENDING

## OQ-006 — What consumes `POST /api/auth/reset/confirm`'s `{ok, email}`?
- raised_by: generator P4
- kind: inferred-only
- readings:
  - A: some downstream system (SSO? the UI?) completes the credential change — evidence:
    none in this repo; `users` has no password column (`ticketd/db/schema.sql:12-16`)
  - B: the endpoint is the whole flow and the returned email is the "proof" — evidence:
    `ticketd/app/server.py:108` returns `{ok: true, email}` and nothing else happens
- blocks: []   (WO-006 implements the observable contract exactly; flags WO-006 gate —
  a repair of token storage (PB-002) should not break an unknown consumer)
- ruling brief: `guide/briefs/OQ-006-ruling-brief.md`
- ruling: PENDING

## OQ-007 — Invalid priority values cause a 500 via DB CHECK: preserve or validate?
- raised_by: generator P4
- kind: ambiguity / pb-proposal
- readings:
  - A: observed contract: priority outside {"1","2","3"} passes through uncoerced
    (`ticketd/app/server.py:47-49`) and any value outside {low,med,high} violates
    `ticketd/db/schema.sql:5` CHECK → unhandled IntegrityError → 500 HTML page
    (confirmed against the pinned legacy boot, trace `ask-priority-500`)
  - B: clients only ever send valid values (UI-controlled), so a 422 would be invisible
    to the UI and strictly better — but PB-005 (no UI changes) makes silent 500→422
    an unsanctioned deviation
- blocks: []   (WO-002 implements A minus the HTML body — see the WO; the 500-class
  status is preserved. Trace `ask-priority-500` sits in the `edge-ask` input set,
  excluded from acceptance until ruled)
- ruling: PENDING

## OQ-008 — Unexplained 5xx in the access log on plain read paths
- raised_by: generator P2
- kind: discrepancy
- readings:
  - A: SQLite write-lock contention under concurrency — evidence: 31×5xx on
    `GET /api/tickets`, 12 on create, 5 on close, 3 on get (`usage-weights.json.status_mix`);
    code has no explicit 500 path
  - B: unhandled exceptions from bad input (e.g. OQ-007's CHECK violation explains POST
    but not GET)
- blocks: []   (informational: Postgres removes the single-writer bottleneck; NFR-2
  measures the outcome. If the team knows these incidents, testimony welcome.)
- ruling: PENDING

## OQ-009 — Access log shows `POST /api/tickets` → 200; code returns 201
- raised_by: generator P2/P9 (evidence conflict)
- kind: discrepancy
- readings:
  - A: code is ground truth: `ticketd/app/server.py:55` returns 201, and the pinned legacy
    boot returns 201 (trace `tickets-create-001`)
  - B: the log's 200s are real: a proxy/LB in front of prod rewrites or the log field is
    not the app status — all 2000 log lines show 200/4xx/5xx, never 201
- blocks: []   (replay goldens captured from the pinned boot are authoritative for L3;
  if prod really serves 200 the UI tolerates both, but worth one human glance)
- ruling: PENDING
