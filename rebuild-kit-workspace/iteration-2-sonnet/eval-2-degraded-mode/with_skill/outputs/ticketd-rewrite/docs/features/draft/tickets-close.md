# Draft spec — Tickets: close (PB-001 site)

<!-- Cross-reference (P9 audit finding I-2): this route is also unauthenticated -- see
     docs/open-questions.md#OQ-004. -->

## POST /api/tickets/<int:tid>/close

- statement: Sets `status = 'closed'`, `closed_at = now()` **only if** the ticket is currently
  not already closed (`WHERE id = ? AND status != 'closed'`); this makes the operation
  idempotent — closing an already-closed ticket is a no-op.
  fidelity: FIXED
  evidence: [legacy/app/server.py:69-71] confidence: cited
- statement: Response is `{"closed": <bool>}` — `true` if a row changed, `false` on the no-op
  case (already closed, or ticket doesn't exist — both produce `changed == 0`, so both produce
  `{"closed": false}` with `200`, not a `404` distinction between "already closed" and "no such
  ticket").
  fidelity: FIXED
  evidence: [legacy/app/server.py:73, 77] confidence: cited
- statement: When (and only when) the status actually transitions, a notification email is sent
  to the fixed address `watchers@example.internal` with subject-less body `"closed: {title}"`.
  fidelity: FIXED (the notification *content and trigger condition*)
  evidence: [legacy/app/server.py:73-76] confidence: cited
- statement: **PB-001** — the notification send is synchronous, in-request
  (`send_mail(...)` called directly in the handler, no queue/background task). SMTP timeout is
  30s (`legacy/app/notify.py:6`); a send failure raises inside the handler with no try/except at
  either call site, so the whole close request fails (Flask default 500) after paying the
  connection-timeout cost, even though the DB transaction already committed the status change
  (`db().commit()` at line 72, *before* the send at line 76) — meaning on SMTP failure the ticket
  IS closed but the client sees a 500 and doesn't know that.
  fidelity: REPAIR — target: the close endpoint returns success as soon as the DB commit
  succeeds; email dispatch happens out-of-band and cannot fail the HTTP response. Mechanism is
  FREE (see `modern/CLAUDE.md`); the outcome (non-blocking, and no more "closed but client sees
  an error") is REPAIR-mandated by PB-001.
  evidence: [legacy/app/server.py:69-77, legacy/app/notify.py:1-7]
  divergence: ED-001 (see verification/replay/expected-divergences.yaml)
