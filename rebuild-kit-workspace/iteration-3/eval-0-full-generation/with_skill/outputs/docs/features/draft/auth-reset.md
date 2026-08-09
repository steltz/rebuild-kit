# Draft: Auth/Reset subsystem (request, confirm)

Feeds WO-001 (notification decoupling, cross-cutting), WO-003 (token mechanism/security), WO-004
(reset endpoints). Entity reference: `docs/domain/reset_token.md`. Citations against
`ticketd/app/server.py` at pinned ref `1cc113597ea87990e731f02190fc6999e42e7cd8`.

## POST /api/auth/reset — request

- **statement**: accepts `{"email": <string>}`; missing key defaults to `""` (empty string is a
  legal, processed value — no validation that it looks like an email at all).
  fidelity: FIXED. confidence: cited (`server.py:82-83`).
- **statement**: rate limit is 3 requests/hour, counted per exact `email` string match against
  `reset_tokens` rows with `created_ts` in the last 3600 seconds; exceeding it returns
  `429 {"error": "rate_limited"}` and **does not mint a token or send an email**.
  fidelity: FIXED. confidence: cited (`server.py:85-89`) + traced (one `429` observed in the
  2,000-row sample, on this exact route — `usage-weights.json` status_mix).
- **statement (PB-008)**: the rate-limit check is skipped entirely — not raised, not
  logged, just bypassed — when the request carries header `X-Internal-Bypass: 1`. No fidelity tag:
  this is the open question itself (OQ-002). WO-004 implements the rate limit as FIXED for the
  normal path; the bypass mechanism's disposition (keep as a sanctioned internal escape hatch,
  drop as dead scaffolding, or replace with a real internal-service auth mechanism) is gated on
  OQ-002's ruling.
- **statement (PB-002)**: token is `hashlib.md5(f"{email}{time.time()}").hexdigest()` — MD5 of
  low-entropy, guessable-if-timing-is-known input. fidelity: **REPAIR in WO-003**. Target: a
  cryptographically random token (e.g. `secrets.token_urlsafe(32)` or equivalent ≥128-bit
  randomness), with only a hash of it persisted server-side (never the raw token after issuance).
  See ED-002. confidence: cited (`server.py:90`).
- **statement (PB-002)**: the token row (`email`, `token`, `created_ts`) is inserted into a table
  with no index, no PK, no expiry sweep — rows for abandoned/expired flows accumulate forever.
  fidelity: **REPAIR in WO-003**. Target: expiry-based cleanup (a scheduled sweep, or a DB-level
  TTL mechanism if the target stack has one available — FREE on mechanism, REPAIR on the
  "bounded storage" outcome). confidence: cited (`server.py:90-93`, `db/schema.sql:18-22`).
- **statement**: on success, sends a synchronous email to the *requested* address (not validated
  as belonging to a real user) with the raw token in the plaintext body
  (`f"reset token: {token}"`), then returns `{"ok": true}` — response only arrives after SMTP
  completes. fidelity: **REPAIR in WO-001** for the synchronous-dispatch part (same PB-001
  mechanism as ticket-close, see ED-001); the *content* of the email (raw token in plaintext body)
  is FIXED — no PB entry authorizes changing what the email says, only when it's sent.
  confidence: cited (`server.py:94-95`) + traced (perf-envelopes.json: this route's p50/p95/p99
  are all elevated versus non-mail-sending routes, consistent with `close`'s pattern).
- **statement**: response body and `200` status are identical whether or not the email address
  corresponds to a real user — no existence disclosure. fidelity: FIXED (security-conscious
  property worth explicit preservation, not just incidental). confidence: cited (`server.py:83-95`
  — no branch anywhere checks `users` table membership).

## POST /api/auth/reset/confirm — confirm

- **statement**: looks up `reset_tokens` by exact `token` string match (missing key defaults to
  `""`, which will simply match no row). fidelity: FIXED. confidence: cited (`server.py:100-102`).
- **statement (deliberate, cited in-code)**: token not found AND token found-but-expired
  (`time.time() - created_ts > 30*60`) return the **identical** response:
  `403 {"error": "invalid_token"}`. Non-disclosure is explicit in a code comment
  (`server.py:104`). fidelity: FIXED — must be preserved exactly, including through whatever new
  token storage mechanism WO-003 builds (the *outcome* "expired and invalid are indistinguishable
  to the caller" is FIXED even though the *storage* is REPAIR). confidence: cited
  (`server.py:103-105`).
- **statement**: on success, the token row is deleted (single-use enforcement) and the response is
  `200 {"ok": true, "email": <the email associated with the token>}` — this is the only endpoint
  in the system that echoes back an email address tied to server-side state.
  fidelity: FIXED. confidence: cited (`server.py:106-108`).
- **statement**: no rate limiting exists on `confirm` itself (only on `request`) — an attacker
  could brute-force tokens without a rate-limit backstop, mitigated only by 30-minute expiry and
  (once WO-003 lands) token entropy. fidelity: FIXED as an observed absence — no PB entry proposes
  adding confirm-side rate limiting, and inventing new protective behavior beyond what
  PB-002/OQ's scope covers would be unsanctioned scope creep. Worth flagging as a possible future
  PB entry, not building it now. confidence: cited (`server.py:98-108`, no rate-limit code present).
