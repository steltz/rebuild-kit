# Integration Notes

## Outbound: SMTP

- **Target**: `smtp.internal:25` (hardcoded, `ticketd/app/notify.py:6`). No TLS visible in the
  `smtplib.SMTP(...)` call (plain SMTP on port 25, not `SMTP_SSL` or `.starttls()`) — worth
  confirming with whoever owns `smtp.internal` whether that's expected for this rewrite or an
  incidental gap; no PB entry addresses it, so it's FIXED (preserve as-is) absent a ruling. Not
  filed as a formal OQ since it's not blocking anything and is easy to raise later.
- **Timeout**: 30s (`notify.py:6`), matching the "30s on provider trouble" documented in the
  module docstring.
- **Auth**: none visible — no `login()` call, so `smtp.internal:25` is presumably an
  unauthenticated relay reachable only from the app's network (internal tool, internal relay).
- **Retry**: none. A failed/timed-out send raises inside `sendmail()`/the `with` block and
  propagates as an unhandled exception (500) to whichever HTTP handler called it, since neither
  call site (`server.py:76`, `:94`) wraps the call in a try/except.
- **Sandbox availability for testing**: none supplied. The rewrite's twin-boot L3 harness
  (`verification/`) will need a fake/stub SMTP server for both trees — real `smtp.internal` isn't
  reachable from a rewrite workspace and shouldn't be, even if it were.
- **Message shapes actually sent** (not a formal schema — these are plain-text bodies, not
  structured payloads):
  - Ticket close: to `watchers@example.internal`, body `f"closed: {title}"` (`server.py:76`).
  - Reset request: to the requester's submitted email, body `f"reset token: {token}"`
    (`server.py:94`) — this is the only place the raw reset token ever appears outside the DB row
    itself; anyone who can intercept this email can complete the reset flow, by design (that's
    what a password-reset email is).

## Inbound: none

No webhooks, no callbacks, no other services call into ticketd beyond the one first-party UI
client observed in the access log (`svc-ui/2.1`). No signature verification scheme exists because
there is nothing to verify.

## Auth / caller identity

No authentication or session mechanism exists anywhere in `ticketd/app/server.py` — every route is
open to any caller that can reach the process. This is presumably mitigated today by network
placement (an "internal" tool). See `docs/open-questions.md#OQ-007` — unresolved, non-blocking for
M0, must be revisited before the new service's network exposure changes from today's.

## Looseness clients may depend on (Hyrum's Law candidates)

- `priority` accepts both `"1"`/`"2"`/`"3"` and free-text strings (`server.py:47-49`) — documented
  in the OpenAPI spec as `anyOf: [string, integer]` rather than a strict enum, because the code
  comment explicitly says both client shapes must keep working.
- `POST` bodies that aren't valid JSON, or are entirely absent, are silently treated as `{}`
  (`request.get_json(silent=True) or {}`, all four POST handlers) rather than rejected — every
  request schema in `docs/contracts/schemas/` is `additionalProperties: true` and has no
  `required` array at the top level for exactly this reason; only individual fields are validated,
  and only where the code actually validates them.
- `GET /api/tickets?status=<anything>` silently accepts values outside `open`/`closed` and just
  matches zero rows — not a 400. Documented as an enum in the OpenAPI param for readability, but
  the *behavior* on an out-of-enum value is "empty result set," not "rejected."
