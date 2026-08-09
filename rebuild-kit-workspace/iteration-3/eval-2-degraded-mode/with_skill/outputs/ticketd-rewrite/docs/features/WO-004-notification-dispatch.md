# docs/features/WO-004-notification-dispatch.md
id: WO-004            depends_on: []                    milestone: M1
risk: 0.55 (inferred-claim ratio low on the DEFECT side [PB-001 is directly cited and
  boot-reproduced: legacy/app/notify.py's own docstring plus a live 500 when SMTP is
  unreachable]; but the TARGET mechanism is FREE and its delivery-guarantee level is an
  unresolved ASK [OQ-002] — that ambiguity plus PB-001's "high" severity plus zero legacy test
  coverage drives risk above the 0.5 gate threshold)
usage_weight: none (degraded)   pain_weight: 1.0 (PB-001, severity high — the sole highest-pain
  item in the problem brief alongside PB-002)   context_budget: ~250 lines   gate: true

behaviors:
  - statement: Provide an async-safe email dispatch boundary that WO-002 (ticket close) and
      WO-003 (auth reset) call instead of legacy's in-request `smtplib.SMTP` call, so neither
      caller's HTTP response blocks on SMTP connect/send (2s typical, 30s timeout, per
      legacy/app/notify.py's own docstring — PB-001).
    fidelity: REPAIR — target: async dispatch (background task, queue, or outbox — mechanism
      FREE per modern/CLAUDE.md, delivery-guarantee level per OQ-002 ruling).
    evidence: [legacy/app/notify.py:1-7, legacy/app/server.py:73-76 (close call site),
      legacy/app/server.py:94 (reset call site), docs/open-questions.md#OQ-002]
      divergence: ED-001, ED-002, ED-003 (verification/replay/expected-divergences.yaml —
      UNRATIFIED, see file header; this WO cannot close its gate until a human signs them)
  - statement: Failures dispatching email must be observable (logged/metriced), since PB-001's
      whole motivation was an operationally invisible failure mode blocking the request thread —
      moving it off the request path must not also move it out of sight.
    fidelity: FREE — outcome required (observable failure), mechanism open.
    evidence: [docs/problem-brief.md#PB-001, modern/CLAUDE.md conventions section]

acceptance:
  replay_set: N/A directly (this WO has no HTTP surface of its own) — validated indirectly
    through WO-002's and WO-003's replay sets, whose `state.email_dispatch.mode` must read
    "queued" per ED-001/002/003, not "sync".
  tests: none of its own; WO-002/WO-003 characterization tests assert against this boundary.
escalation: consult legacy/app/notify.py:1-7 only; do not read legacy/app/server.py's call
  sites beyond what WO-002/WO-003 already cite.

## Gate note

`gate: true` because: (a) OQ-002's delivery-guarantee ambiguity is unresolved, (b) the
expected-divergence entries this WO's acceptance depends on are UNRATIFIED (generated
non-interactively, no human available — see docs/problem-brief.md), and (c) PB-001 is a
brief-cited "high" severity defect, so its fix deserves explicit sign-off before WO-002/WO-003
(which both depend on this WO) can proceed past it.
