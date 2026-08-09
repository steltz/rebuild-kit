# WO-004 — Close ticket + decoupled notification (the PB-001 repair)

id: WO-004            depends_on: [WO-001]          milestone: M1
risk: 0.68 (REPAIR of the rewrite's founding defect; PB-001 severity high; new infra —
  outbox + worker; divergence-verified rather than trace-matched)
usage_weight: 0.0495  pain_weight: 0.40             context_budget: ~400 lines   gate: true

Reading list: this file · `docs/contracts/openapi.yaml` (close) ·
`docs/contracts/schemas/mail-message.schema.json` · `docs/migration/target-schema.sql`
(mail_outbox) · `verification/replay/expected-divergences.yaml#ED-001` ·
`docs/open-questions.md#OQ-004` · `verification/harness/README.md`.

behaviors:
  - statement: POST /api/tickets/<int:tid>/close sets status='closed', closed_at=now, only
      when status != 'closed' (WHERE-guarded; idempotent). Request body ignored entirely.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:67-72, traces: t2-core#tickets-close-001/002]
  - statement: response is always 200 {"closed": <bool>} — true iff a row transitioned;
      false for already-closed AND nonexistent ids (indistinguishable to the caller).
    fidelity: FIXED
    evidence: [ticketd/app/server.py:73,77, traces: tickets-close-001..003]
  - statement: on actual transition only, exactly one mail: from ticketd@example.internal,
      to watchers@example.internal, body exactly "closed: <title>" (headerless raw body).
    fidelity: FIXED (content/recipient/cardinality)
    evidence: [ticketd/app/server.py:73-76, ticketd/app/notify.py:6-7, trace: tickets-close-001 state.email]
  - statement: legacy sends that mail synchronously in-request (SMTP, 30s timeout) — the
      June-outage mechanism.
    fidelity: REPAIR (PB-001) — target: the close request commits and responds without any
      SMTP dependency; the mail is dispatched at-least-once by a decoupled mechanism.
      Default mechanism (FREE, OQ-004 unruled): mail_outbox row written in the SAME
      transaction as the close + a worker delivering to SMTP with retry. Record the choice
      in ledger free_choices.
    evidence: [ticketd/app/server.py:76 (comment), ticketd/app/notify.py:5-7, PB-001]
    divergence: ED-001 (state.email.mode sync → queued)
  - statement: NFR-1 — close keeps working with SMTP fully down.
    fidelity: REPAIR outcome check (PB-001)
    evidence: [PB-001 (June outage, 40 min)]

acceptance:
  replay_set: tickets-close-001..003 + tickets-list-005 from t2-core (ED-001 applies)
  tests: verification/characterization/test_tickets.py::test_close_idempotent_and_notifies,
         ::test_close_missing_ticket_closed_false (CHAR_TARGET=modern; wait_mail covers the
         queued window)
  nfr: with the worker's SMTP target unreachable, POST close must return 200 within the
       NFR-2 envelope (p95 ≤ 287ms without the legacy mail tax — expect far lower) and the
       outbox row must survive for later delivery.
escalation: consult ticketd/app/server.py:67-77 only on ambiguity.
