# Draft Feature Spec — Auth/Reset (request / confirm)

Subsystem: Auth/Reset (`docs/00-overview.md`). All confidence tags are `cited` unless noted
`inferred`. Self-verification pass completed against `legacy/app/server.py:80-108` a second time
before finalizing (serial fallback for P4's paired extract-and-verify).

## POST /api/auth/reset — request

1. Reads `email` from JSON body (`request.get_json(silent=True) or {}`); missing key defaults to
   `""` — no email-format validation anywhere in this handler.
   fidelity: FIXED · evidence: `legacy/app/server.py:82-83`
2. **Rate limit**: if header `X-Internal-Bypass` is NOT exactly `"1"`, counts reset_tokens rows
   for this `email` created within the last hour (`created_ts > now - 3600`); if count >=
   `RATE_LIMIT_PER_HOUR` (3), returns `429 {"error": "rate_limited"}` and stops.
   fidelity: FIXED · evidence: `legacy/app/server.py:84-89`
3. **Bypass**: if header `X-Internal-Bypass` equals exactly `"1"`, the rate-limit check above is
   skipped entirely — unlimited reset requests for any email. Undocumented anywhere else in the
   codebase; no auth/allowlist gates who can send this header.
   fidelity: FIXED (preserve — no PB backs removing it) · confidence: cited · evidence:
   `legacy/app/server.py:84` · **pb-proposal filed: OQ-004** — intent unconfirmed; WO-001
   defaults to porting the bypass disabled-by-default in `modern/` config until ruled.
4. Token generation: `hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()`.
   fidelity: **REPAIR** (PB-002: MD5, low-entropy guessable input) · target: cryptographically
   secure random token (see WO-001, `modern/CLAUDE.md` architecture rules) · evidence:
   `legacy/app/server.py:90`
5. Row inserted into `reset_tokens` (`email`, `token`, `created_ts = time.time()`); no
   uniqueness check against existing tokens for the same email — multiple valid tokens can
   coexist for one email.
   fidelity: FIXED · evidence: `legacy/app/server.py:91-93`
6. **Email sent synchronously in-request** to the user-supplied `email` with the raw token in
   the body: `f"reset token: {token}"` — plaintext, no templating, no expiry note in the message
   itself.
   fidelity: **REPAIR** (PB-001: sync email) · target: enqueue, don't send in-request — same
   target mechanism as the ticket-close email (WO-002 covers both call sites) · evidence:
   `legacy/app/server.py:94`, `legacy/app/notify.py:1-7`
7. Success response: `200 {"ok": true}` — returned even though the request commits the DB write
   AND performs the blocking email send first; a slow/failed SMTP send currently has no visible
   effect on this response (no try/except around `send_mail` — an SMTP exception would propagate
   as an unhandled 500, not a graceful degradation). Confidence: inferred (no explicit error
   handling to cite; absence of a try/except is the evidence).
   fidelity: FIXED (the happy-path 200 shape) — but the "no error handling on send failure"
   behavior is exactly the shape PB-001's REPAIR (WO-002) is meant to eliminate, since an
   enqueue-based flow will return 200 immediately with delivery no longer being a request-time
   concern at all.
   evidence: `legacy/app/server.py:80-95` (absence of exception handling)

## POST /api/auth/reset/confirm — confirm

1. Looks up `reset_tokens` by exact `token` match from the JSON body (missing key defaults to
   `""`, which will simply not match any row).
   fidelity: FIXED · evidence: `legacy/app/server.py:100-102`
2. **Non-disclosure**: both "token not found" and "token found but expired (>30 min old)" return
   the exact same response — `403 {"error": "invalid_token"}`. Explicit comment: "deliberate:
   expired and invalid tokens return the SAME body (non-disclosure)."
   fidelity: FIXED, high confidence (explicit comment + simple, unambiguous branch) · evidence:
   `legacy/app/server.py:103-105`
3. On success: deletes the token row (single-use enforcement via deletion, not a `used` flag),
   commits, returns `200 {"ok": true, "email": <email from the token row>}`.
   fidelity: FIXED · evidence: `legacy/app/server.py:106-108`
4. No re-issuance of a session/credential of any kind happens here — confirming a reset token
   only returns the associated email; there is no password field anywhere in the schema and no
   subsequent "set new password" step in this codebase. Whatever consumes this response to
   actually change a password is outside `legacy/` as handed over.
   fidelity: FIXED (scope boundary, not a behavior to change) · confidence: cited (absence —
   `db/schema.sql` has no password column; no route sets one) · evidence: `legacy/db/schema.sql:12-16`

## Cross-cutting

- Same "no auth on any route" note as the Tickets feature applies here too — anyone can call
  `POST /api/auth/reset` for any email address and receive a 200 (rate-limited, but not
  authenticated). This is how password-reset flows conventionally work (request-by-email is
  meant to be public), so it is NOT flagged as an anomaly the way the CSV export's lack of auth
  is — noted for completeness only.
