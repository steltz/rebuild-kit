# notification (how it works today)

Seven lines that caused a rewrite (`ticketd/app/notify.py`). Every mail — close
notifications, reset tokens — opens a fresh SMTP connection to `smtp.internal:25` with a
**30-second timeout**, inside the HTTP request that triggered it, with no retry and no
queue. When SMTP is slow, requests are slow; when SMTP is down, the requests 500 — which
in June meant closing tickets was down for 40 minutes (PB-001).

Details worth knowing:
- The message is a *headerless raw body* — no Subject line, no headers at all
  (`ticketd/app/notify.py:7`, NT-2). Whatever renders these mails today copes with that;
  the rewrite keeps the body format (changing it would need a PB sanction).
- The close route commits *before* sending (CL-6), so a ticket can close and the mail
  still be lost — delivery was already best-effort; it was just best-effort *and*
  blocking.
- Observed cost: close p50 is 110ms vs ~25ms for reads (`perf-envelopes.json`) — the
  SMTP tax. (The docstring's "~2s typical" overstates vs the 30-day envelope; the
  envelopes are authoritative — audit report, coverage notes.)

The repair (ED-001/ED-003, WO-004): dispatch decouples from the request path — default
mechanism a Postgres transactional outbox plus delivery worker (OQ-004 lets the team
redirect this choice). Same sender, same recipients, same bodies; only the *when and how*
of delivery changes, and NFR-1 requires ticket operations to sail through an SMTP outage.
