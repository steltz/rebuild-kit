id: WO-002            depends_on: [WO-001]                milestone: M1
risk: 0.68 (PB severity high — this is the literal reason leadership approved the rewrite;
  inferred-claim ratio low, real behavior is well-evidenced; complexity: architectural FREE
  choice with real consequences (in-process BackgroundTasks vs. a durable queue/outbox);
  legacy coverage: none; no direct trace-level acceptance for the mechanism itself, see below)
usage_weight: 0.0495+0.0195 = 0.069 (tickets-close + auth-reset-request combined — this WO is
  infra those two routes consume, not a route itself)
pain_weight: 0.9 (PB-001, severity high, the incident that triggered the whole rewrite)
context_budget: ~300 lines (this WO + docs/problem-brief.md PB-001 + modern/CLAUDE.md
  architecture rules + docs/open-questions.md OIQ-1)
gate: true

## What this WO does
Build the out-of-band notification dispatch mechanism PB-001 requires: no request handler may
perform network I/O to the mail transport synchronously. This WO delivers the mechanism only
(a `notify(to, body)` interface any handler can call that returns immediately and guarantees
delivery happens out-of-band); WO-004 (close) and WO-003/WO-007 (reset) are the call sites that
consume it. Building it once, here, keeps both call sites consistent and testable against one
contract instead of two independent async hacks.

behaviors:
  - statement: "A downed or slow mail transport must never make POST /api/tickets/{id}/close
      or POST /api/auth/reset fail, hang, or exceed a request-time budget dependent on SMTP
      round-trip time."
    fidelity: REPAIR — target ratified by PB-001 (leadership testimony: the June SMTP outage
      took ticket-closing down for 40 minutes because email was sent synchronously in-request).
    evidence: [docs/problem-brief.md PB-001, legacy/app/notify.py:1,6, legacy/app/server.py:73-76,94]
    divergence: ED-001 (see verification/replay/expected-divergences.yaml's notes — this
      harness's trace format does not yet carry dispatch-mode as a comparable field; closing
      this WO requires EITHER extending the trace schema with an explicit notification-state
      field OR accepting that ED-001 is verified by a dedicated unit/integration test in
      characterization/, not by L3 trace diff. Pick one and record the choice in ledger notes —
      this is a genuine open implementation decision this WO must resolve, not defer.)
  - statement: "Delivery mechanism: FastAPI BackgroundTasks (simplest, sufficient for outcome
      parity) vs. a durable queue/outbox (stronger at-least-once guarantee, more infra)."
    fidelity: FREE — outcome required (async, non-blocking); mechanism choice depends on
      OIQ-1 (no numeric SLO was given for how strong the delivery guarantee needs to be).
      Default recommendation absent a ruling: BackgroundTasks first (M1), upgrade to a durable
      queue later if OIQ-1 gets ruled to require at-least-once delivery — record whichever is
      chosen in ledger.json free_choices.
  - statement: "The notification CONTENT (recipient, body text) for each call site is
      unchanged from legacy: close sends to the hardcoded watchers@example.internal with body
      f'closed: {title}'; reset sends to the requesting email with body f'reset token: {token}'."
    fidelity: FIXED — content/recipients are not what PB-001 asks to change, only the dispatch
      timing/mechanism. Do not touch these while building the async wrapper.
    evidence: [legacy/app/server.py:76,94]

acceptance:
  replay_set: none directly (this WO delivers infra; see divergence note above on why L3
    doesn't yet exercise this WO's actual behavior change on its own)
  tests: a NEW characterization test asserting (a) the calling request returns successfully
    within a tight latency budget even when the mail transport is deliberately made
    slow/unavailable in the test harness, and (b) the notification is eventually observed
    (e.g. in a test double / captured queue) — this is the real acceptance bar for this WO,
    write it as part of closing this WO since no pre-existing golden trace covers it
  l1: n/a (no new HTTP contract surface)
  l3: exercised indirectly once WO-004/WO-003 land and their replay sets run

escalation: consult legacy/app/notify.py (7 lines) and legacy/app/server.py:73-76,94 in full —
  small enough that "escalation" here just means reading the two real call sites once.
