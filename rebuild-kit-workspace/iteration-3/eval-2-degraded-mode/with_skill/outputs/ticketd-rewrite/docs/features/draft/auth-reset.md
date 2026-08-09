# Draft — Auth/Reset subsystem

<!-- P4 draft, self-verified against legacy/app/server.py line-by-line on 2026-08-09.
     Confidence: all claims below are `cited`. None are `traced` (no runtime capture available
     this run). -->

## Feature: Request reset — `POST /api/auth/reset`

- statement: Accepts `{"email": <str>}`; missing `email` defaults to `""` (empty string) rather
  than rejecting the request — an empty-email reset request is processed like any other value,
  rate-limited and (if under the limit) issued a token and "sent" to an empty address.
  fidelity: FIXED — no validation exists; not brief-flagged, so not a REPAIR target. Flagged as
  a candidate PB-proposal (empty/malformed email is arguably a defect) but not decided here —
  add to `docs/open-questions.md` if the human ruling wants it addressed; currently out of scope.
  evidence: legacy/app/server.py:82-83 (cited)
- statement: Unless the request carries header `X-Internal-Bypass: 1`, the request is rate
  limited to `RATE_LIMIT_PER_HOUR` (3) requests per `email` value within a rolling 1-hour window
  (`created_ts > now - 3600`, counted from `reset_tokens`); over the limit returns
  `429 {"error": "rate_limited"}`.
  fidelity: FIXED for the rate-limit mechanic itself (count/window/response shape).
  evidence: legacy/app/server.py:16-17, 84-89 (cited)
- statement: The `X-Internal-Bypass: 1` header, if present with that exact value, skips the rate
  limit entirely. No authentication or authorization gates this header — any caller can send it.
  fidelity: **ASK** — `docs/open-questions.md#OQ-001`. Two readings (deliberate internal escape
  hatch that needs proper authn vs. leftover debug scaffolding that should be dropped); no PB
  entry or brief testimony resolves which. Blocks WO-003 until ruled.
  evidence: legacy/app/server.py:84 (cited)
- statement: Token is generated as `hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()` —
  a hash of a value that is either attacker-known (email, if targeting a specific account) or
  narrowly-guessable (server wall-clock time at request handling, which an attacker can bound
  tightly by observing response timing), not a value drawn from a CSPRNG.
  fidelity: **REPAIR** — PB-002. Target: generate the token from a CSPRNG (e.g.
  `secrets.token_urlsafe(32)` or equivalent), sized so brute-force/guessing is computationally
  infeasible. The externally observable *outcome* (opaque single-use token string, 30-minute
  validity, non-disclosure on failure) is FIXED; the *generation mechanism* changes.
  evidence: legacy/app/server.py:90 (cited)   divergence: pending ED entry (P8/P9)
- statement: The token is stored in `reset_tokens` alongside `email` and `created_ts`; the table
  has no primary key and no UNIQUE constraint on `token` — nothing at the DB layer prevents a
  duplicate token being stored (probabilistically near-impossible under MD5+timestamp, but not
  structurally prevented).
  fidelity: FREE — outcome required (each issued token must be usable to redeem exactly once,
  see confirm behavior below); the storage/uniqueness mechanism is a rewrite implementation
  choice, not an observable API behavior. Rationale: no client ever observes table structure.
  evidence: legacy/db/schema.sql:18-22 (cited)
- statement: After successful issuance, sends a synchronous notification email to the requested
  `email` with body `f"reset token: {token}"`, blocking the request on SMTP — the same defect
  as the ticket-close notification, second call site.
  fidelity: **REPAIR** — PB-001 (same disposition as the tickets-close instance; see
  `docs/features/draft/tickets.md`). Target: async dispatch, mechanism FREE per OQ-002.
  evidence: legacy/app/server.py:94, legacy/app/notify.py:1-7 (cited)   divergence: pending ED
  entry (shared with the close-ticket instance, or split — P8 decides WO granularity)
- statement: Success response is `200 {"ok": true}` regardless of whether the email address is
  real/deliverable — the endpoint never reveals whether an account exists for that email
  (a form of non-disclosure, though weaker than the confirm endpoint's, since rate-limit
  responses do differ by email-request-count).
  fidelity: FIXED
  evidence: legacy/app/server.py:95 (cited)

## Feature: Confirm reset — `POST /api/auth/reset/confirm`

- statement: Accepts `{"token": <str>}`; missing token defaults to `""`, which will simply not
  match any stored row.
  fidelity: FIXED
  evidence: legacy/app/server.py:100-102 (cited)
- statement: A token that doesn't exist in `reset_tokens`, OR exists but was created more than
  `RESET_WINDOW_MIN` (30) minutes ago, returns the **identical** response:
  `403 {"error": "invalid_token"}`. This is explicitly commented as deliberate: "expired and
  invalid tokens return the SAME body (non-disclosure)".
  fidelity: FIXED — this is the one place legacy intent is explicit and must be preserved
  exactly, including under the new CSPRNG token generation (PB-002/REPAIR does not change this
  redemption-side behavior).
  evidence: legacy/app/server.py:103-105 (cited)
- statement: A valid, unexpired token is deleted from `reset_tokens` immediately upon successful
  confirm (before returning) — making it single-use. There is no separate "used" flag; deletion
  is the mechanism.
  fidelity: FIXED for the outcome (single-use, enforced); FREE for the deletion-vs-flag
  mechanism if the rewrite's storage layer differs (e.g. a soft-delete/used-flag table design is
  an acceptable substitute as long as a second confirm with the same token still gets the
  identical `403 invalid_token` response).
  evidence: legacy/app/server.py:106 (cited)
- statement: Success response is `200 {"ok": true, "email": <str>}` — echoes the email the token
  was issued for. This is the *only* endpoint in the whole app that reveals an email address back
  to the caller, and only after proving possession of a valid token for it.
  fidelity: FIXED
  evidence: legacy/app/server.py:108 (cited)
