# Draft spec: POST /api/tickets/<id>/close

usage_weight: 0.0495 · perf envelope (low-confidence log): p50 110ms / p95 287ms / p99 352ms —
notably ~4-4.5x slower than the list/create routes' p50 ~24-25ms, consistent with (not proof
of, given the log's synthetic nature) the synchronous SMTP call on this path. See
`perf-envelopes.json.confidence_note`.

## Behaviors

- statement: `UPDATE tickets SET status='closed', closed_at=? WHERE id=? AND status != 'closed'`
    — only rows not already closed are affected; `rowcount` (`changed`) reflects whether this
    specific call actually transitioned the ticket.
  fidelity: FIXED
  evidence: [legacy/app/server.py:69-71]
  confidence: cited

- statement: Response is always `200 {"closed": <bool>}` — `true` if this call transitioned the
    ticket, `false` if the ticket was already closed OR did not exist. Both "already closed"
    and "nonexistent id" collapse into the same `false` signal with no way to distinguish them
    from the response alone.
  fidelity: FIXED — not brief-flagged as a defect, and PB-005 freezes the response contract.
  evidence: [legacy/app/server.py:69-77]
  confidence: cited

- statement: On a successful transition (`changed` truthy), a notification email is sent to the
    hardcoded address `watchers@example.internal` with body `f"closed: {row['title']}"`,
    **synchronously, inside the request**, before the response is returned.
  fidelity: REPAIR in WO-002 — target: dispatch asynchronously/out-of-band; the request must
    return successfully regardless of mail-transport availability (PB-001).
  evidence: [legacy/app/server.py:73-76, legacy/app/notify.py:1-7]
  confidence: cited (also traced: the perf envelope's close-route latency profile is
    circumstantially consistent with this synchronous call, though the access log itself is
    low-confidence per `usage-weights.json.notes`)
  divergence: ED-001 (to be finalized once WO-002's exact delivery-guarantee mechanism is chosen)

- statement: If the ticket is already closed or doesn't exist (`changed` is 0/false), **no**
    email is sent (the `if changed:` guard at line 73 skips the notification entirely).
  fidelity: FIXED — this guard must be preserved exactly under the REPAIR: only a genuine
    open→closed transition triggers a notification, not every close-attempt.
  evidence: [legacy/app/server.py:73-76]
  confidence: cited

- statement: **Added after P9 audit — the CURRENT failure mode was implied but never stated as
    its own line item.** Today, if `send_mail` raises (SMTP outage, DNS failure, connection
    refused, timeout — the exact June-incident scenario), the exception is uncaught: the DB
    UPDATE has already committed (`server.py:69-72`, before the `send_mail` call at line 76),
    so the ticket IS closed in the database, but the client receives a 500 instead of
    `200 {"closed": true}` — a successful state change reported as a failure. This is the
    precise mechanism PB-001 names ("closing tickets was down for 40 minutes"): not that
    tickets failed to close, but that the operation *appeared* to fail (and, under sustained
    outage, requests piled up against the 30s SMTP timeout — `notify.py:6` — which is the
    actual "down for 40 minutes" experience).
  fidelity: FIXED (this is the CURRENT, pre-REPAIR behavior — documented so WO-002/WO-004's
    "before" state is explicit, not just implied by PB-001's prose)
  evidence: [legacy/app/server.py:69-76, legacy/app/notify.py:1,6]
  confidence: traced (P9 audit finding — the DB-commits-before-mail-attempt ordering was not
    previously called out explicitly, even though both individual facts were already cited)

## Acceptance
  replay_set: tickets-close-*.jsonl (open→closed transition, already-closed no-op, nonexistent
    id no-op) — each must assert the modern app's *response* matches while the *notification
    dispatch mechanism* diverges as specified in ED-001 (async, not sync)
  tests: characterization/tickets/close.spec
