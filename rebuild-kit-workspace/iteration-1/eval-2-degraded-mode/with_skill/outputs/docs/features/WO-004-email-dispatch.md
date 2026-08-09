# WO-004 — Email dispatch subsystem (the PB-001 repair mechanism)

id: WO-004            depends_on: [WO-001]    milestone: M1
risk: 0.60 (REPAIR mechanism with a FREE design choice; durability semantics matter;
  no legacy analogue to crib from)          gate: true (design review before dependents build on it)
usage_weight: n/a (infrastructure)   pain_weight: 0.5 (PB-001, severity high)
context_budget: ~350 lines (this WO + draft/notifications.md + schemas/email-dispatch.schema.json
  + harness/README.md#modern-boot-contract + modern/CLAUDE.md)

## Scope
The dispatch seam both notification call sites (WO-005, WO-006) use. No email is ever sent
inside a request handler (PB-001). This WO builds the mechanism + the harness observability;
the call sites land in their own WOs.

behaviors:
  - statement: Dispatch API accepts (kind, to, content-parts) and returns after DURABLY
      recording the send intent — request outcome must not depend on SMTP availability.
    fidelity: REPAIR — PB-001 target ("emails must not block or fail requests");
      divergences ED-001/ED-002 assert mode=queued at the call sites.
    evidence: [ticketd/app/notify.py:1-7 (current blocking behavior),
      ticketd/app/server.py:72-76,93-94 (the two call sites + commit-before-send hazard)]
  - statement: Mechanism choice — transactional outbox table + background sender is the
      recommended shape (survives crashes; ties dispatch to the triggering transaction);
      FastAPI BackgroundTasks is the floor, acceptable only with the tradeoff recorded.
    fidelity: FREE — record the choice + rationale in ledger free_choices; design reviewed
      at this WO's gate.
  - statement: Messages are well-formed MIME with proper headers via env-configured
      transport; content must include the classifier-visible markers (`closed: <title>`,
      `reset token: <token>`) so harness classification works (DNP-003 bans the headerless
      raw-body artifact, not the content markers).
    fidelity: FREE (format) / FIXED (content markers + recipients, asserted per call site)
    evidence: [verification/harness/README.md#modern-boot-contract]
  - statement: Under HARNESS=1, dispatched events are observable at /__harness__/emails in
      dispatch order with mode=queued, matching email-dispatch.schema.json.
    fidelity: FIXED (harness API)
    evidence: [docs/contracts/schemas/email-dispatch.schema.json]

acceptance:
  replay_set: none directly (ED-001/ED-002 verified via WO-005/WO-006 replay sets)
  tests: modern/tests unit coverage: durable-record-then-send, SMTP-down does not affect
    caller, events visible under HARNESS=1
gate_packet: guide/briefs/gate-WO-004.md — chosen mechanism, durability semantics, failure
  modes, retry policy
escalation: ticketd/app/notify.py (7 lines) — the entirety of what it replaces
