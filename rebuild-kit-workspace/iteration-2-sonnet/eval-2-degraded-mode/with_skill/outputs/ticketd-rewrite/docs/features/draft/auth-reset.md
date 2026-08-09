# Draft spec — Auth: password reset request + confirm (PB-002 site)

<!-- Cross-references (P9 audit finding I-2): docs/open-questions.md#OQ-004 (no auth/session
     layer anywhere in this app, reset flow included) and docs/open-questions.md#OQ-006
     (reset_tokens rows are never purged -- relevant to the INSERT statement below). -->

## POST /api/auth/reset

- statement: Reads `email` from the JSON body (no validation of email shape; missing key
  defaults to `""`).
  fidelity: FIXED
  evidence: [legacy/app/server.py:82-83] confidence: cited
- statement: Rate limit of 3 requests/hour per email, counted from `reset_tokens` rows for that
  email with `created_ts` in the last 3600s. Over limit -> `429 {"error": "rate_limited"}`.
  fidelity: FIXED
  evidence: [legacy/app/server.py:85-89] confidence: cited
- statement: The rate limit is skipped entirely when the request carries header
  `X-Internal-Bypass: 1` — undocumented anywhere else in the codebase.
  fidelity: FIXED (it's real, evidenced code) — flagged ASK, see `docs/open-questions.md#OQ-007`
  evidence: [legacy/app/server.py:84] confidence: cited
- statement: **PB-002** — token is `hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()`.
  Low-entropy input (email + wall-clock float), fast hash, no CSPRNG.
  fidelity: REPAIR — target: `secrets.token_urlsafe(32)` or equivalent CSPRNG output, no
  hashing of predictable input. Outcome contract to preserve: single-use, opaque, exchanged for
  identity only via the confirm endpoint below.
  evidence: [legacy/app/server.py:90] divergence: ED-002
- statement: Token, email, and `created_ts = time.time()` are inserted into `reset_tokens`
  (no primary key on this table — see `docs/domain/reset-token.md`).
  fidelity: FIXED (storage shape) — mechanism (PK, indexing) is FREE for the Postgres schema.
  evidence: [legacy/app/server.py:91-93, db/schema.sql:18-22] confidence: cited
- statement: A notification email containing the raw token is sent to the requesting `email`,
  synchronously, in-request — same PB-001 defect as the close endpoint (this is the *second*
  call site of the same underlying problem).
  fidelity: REPAIR (PB-001) — same target/mechanism as tickets-close.md's REPAIR entry.
  evidence: [legacy/app/server.py:94, legacy/app/notify.py:1-7] divergence: ED-001
- statement: Success response is always `200 {"ok": true}` regardless of whether `email`
  corresponds to a real user (no `users` lookup occurs at all in this flow — consistent with
  `users` being dead code, `docs/open-questions.md#OQ-003`).
  fidelity: FIXED
  evidence: [legacy/app/server.py:95] confidence: cited

## POST /api/auth/reset/confirm

- statement: Looks up `reset_tokens` by exact `token` match.
  fidelity: FIXED
  evidence: [legacy/app/server.py:100-102] confidence: cited
- statement: Not-found AND expired (`now - created_ts > 1800s`, i.e. `RESET_WINDOW_MIN=30`) both
  return the **identical** body: `403 {"error": "invalid_token"}`. Comment confirms this is
  deliberate non-disclosure, not an oversight.
  fidelity: FIXED — preserve exactly; do not "improve" this into two distinct error codes/bodies.
  evidence: [legacy/app/server.py:103-105] confidence: cited
- statement: On success, the token row is deleted (single-use enforced) and the response is
  `200 {"ok": true, "email": <str>}`.
  fidelity: FIXED
  evidence: [legacy/app/server.py:106-108] confidence: cited
