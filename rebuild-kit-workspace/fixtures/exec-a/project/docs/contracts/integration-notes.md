# Integration notes — outbound dependencies, boundary looseness

## Outbound: SMTP

- **Target**: `smtp.internal:25`, plaintext SMTP, no TLS/auth configured in code
  (`ticketd/app/notify.py:6`).
- **Timeout**: 30 seconds (`smtplib.SMTP(..., timeout=30)`), per-call, no retry logic anywhere.
- **Call sites**: `close_ticket` (`server.py:76`), `request_reset` (`server.py:94`) — both
  synchronous, in-request (PB-001).
- **Sandbox availability**: none in this evidence base — `smtp.internal` does not resolve
  outside the original production network. The verification harness stubs this call entirely
  (module-attribute monkeypatch at runtime, not a code edit) rather than attempting to reach a
  real or fake SMTP server — see `verification/harness/README.md`. Anyone standing up a local
  dev environment for `modern/` will need either a real SMTP relay, a local dev SMTP catcher
  (e.g. MailHog/Mailpit), or the same kind of stub, depending on which async mechanism WO-002
  chooses.
- **No webhooks received.** No inbound integration of any kind was found — every route is a
  direct client-initiated HTTP call, nothing arrives from an external system.

## HTTP boundary looseness (Hyrum's law candidates)

Per `docs/contracts/openapi.yaml`, the following places where the legacy app accepts *more*
than a strict reading of its own documented contract would suggest — clients may depend on the
looseness, so it's called out rather than silently tightened:

- **`priority` accepts extra shapes.** Both `"1"/"2"/"3"` and `low/med/high` are accepted and
  coerced — a code comment (`server.py:46`) confirms this is intentional compatibility, not
  incidental looseness. Preserve both.
- **`status` filter on `GET /api/tickets` accepts any string**, not just `open`/`closed` — a
  non-matching value simply returns zero rows rather than a 400. A client sending an unexpected
  status value (typo, stale enum) fails silently rather than loudly; preserve this exactly
  (changing it to a 400 would be new, unrequested strictness).
- **No `Content-Type` enforcement observed** — Flask's `request.get_json(silent=True)` will
  attempt to parse the body regardless of the `Content-Type` header in some configurations;
  this wasn't independently verified against the actual legacy behavior (would need a dedicated
  trace) and is flagged as a gap in this integration-notes pass, not asserted as fact.
- **Numeric vs. string JSON types are NOT coerced beyond the documented `priority` case** — e.g.
  `id` in `GET /api/tickets/{id}` must be a genuine JSON path integer per Flask's `<int:tid>`
  converter; a numeric-looking string in the URL still works (URL paths are always strings,
  Flask converts), but a non-integer segment produces Flask's plain 404 (see
  `docs/features/draft/tickets-get.md` and its x-legacy-note in `openapi.yaml`).

## What's NOT here

No auth scheme is documented in `openapi.yaml` because none exists in the legacy app — see
`docs/open-questions.md` OQ-002. No rate-limit headers, no pagination headers/links (the list
endpoint has neither pagination nor rate limiting). No API versioning scheme.
