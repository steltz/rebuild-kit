# Draft: Notifications (cross-cutting)

Feeds WO-001. Not a route — a library (`ticketd/app/notify.py`) called from two sites in the
Tickets and Auth/Reset subsystems. This is the single subsystem PB-001 is about.

## send_mail(to, body)

- **statement**: opens a new `smtplib.SMTP("smtp.internal", 25, timeout=30)` connection per call
  (no connection reuse/pooling), sends via `sendmail()`, and the `with` block closes it.
  fidelity: FREE — connection-per-call vs. pooled/persistent is an implementation detail; no
  behavior depends on which one is chosen as long as the message is delivered. confidence: cited
  (`notify.py:5-7`).
- **statement**: docstring records observed latency characteristics: "~2s typical, 30s on provider
  trouble" (`notify.py:1`) — the 30s figure matches the configured `timeout=30`
  (`notify.py:6`), i.e. worst case this call blocks its caller for a full 30 seconds before the
  `smtplib` timeout itself fires (and even then, an unhandled `TimeoutError`/`SMTPException` would
  propagate up as a `500` to the original API caller — no try/except exists anywhere around either
  call site). fidelity: this latency profile is exactly what PB-001 is about — REPAIR in WO-001,
  target: no caller of `send_mail`-equivalent functionality ever waits on it synchronously.
  confidence: cited (`notify.py:1,6`) + traced (perf-envelopes.json p99s on both call-site routes
  cluster around 300-350ms even in the same-day healthy-provider sample — nowhere near the 30s
  worst case, but already 3-5x the non-mail routes' p50, consistent with the "~2s typical"
  documented figure occasionally showing up even under normal conditions... actually the observed
  p99s (~300-350ms) are well under 2s, so the sample here reflects "typical," not "provider
  trouble" conditions; the 30s worst case is documented but not observed in this evidence window).
- **statement**: sender address is hardcoded (`ticketd@example.internal`, `notify.py:7`).
  fidelity: FIXED — no PB entry proposes changing it, and it's a cosmetic/identity detail with no
  behavioral consequence for callers. confidence: cited.
- **statement**: no retry logic, no dead-letter/failure queue, no delivery confirmation beyond
  `smtplib` not raising. A failed send (SMTP down, rejected recipient, etc.) currently means: for
  `close_ticket`, the DB transition already committed (`server.py:72`, commit happens *before* the
  send) so the ticket *is* closed even if the notification fails outright — only the *notification*
  is lost, not the state change; for `request_reset`, same ordering (`server.py:93` commit before
  `:94` send), so a token *is* usable even if its notification email never arrives (the user just
  never finds out the token exists, unless the client surfaces the `200 {"ok": true}` in some other
  way). fidelity: this ordering (state change durable, notification best-effort) is worth
  preserving as an outcome — REPAIR target for WO-001 should keep "the business transaction
  succeeds independent of notification delivery," just move notification off the request's
  critical path AND make it durable across restarts (an outbox/queue, not fire-and-forget) so a
  crash between commit and send doesn't silently drop the notification the way a crash in the
  legacy code between `server.py:93` and `:94` already can. confidence: cited
  (`server.py:72-76`, `:93-95`) — the "crash silently drops the notification" failure mode is
  inferred from the code structure, not traced (no evidence of it actually happening was
  supplied); noted as a design requirement for WO-001, not a claim about legacy production
  incidents beyond the one PB-001 already describes.
