# Draft spec — subsystem: auth-reset

<!-- P4 draft. Confidence: cited | inferred | traced T2 (observed via the harness against
     the pinned legacy). Degraded mode: no T1/production evidence exists.
     AUDIT NOTE (P9): rate-limit semantics corrected per finding A-01; purge FREE-grant
     narrowed per A-02; non-object/non-string input paths added per A-04/A-13. -->

## Feature: request reset — POST /api/auth/reset

- statement: `email` is taken from the JSON body with default `""`; it is **never validated**
  — not for format, not against `users`. A reset can be requested for any string, including
  empty, and the response is `{"ok": true}` regardless of whether the email is known.
  fidelity: FIXED (the always-ok response is account-enumeration-safe and plausibly deliberate;
  the empty-string acceptance rides along) — see OQ-002 for what the flow is even *for*.
  confidence: cited   evidence: ticketd/app/server.py:82-95
- statement: Rate limit — a request is rejected (429 `{"error":"rate_limited"}`) when ≥3
  rows for that email currently exist in `reset_tokens` with `created_ts > now-3600`. The
  count is over SURVIVING rows, not past requests: confirming a token DELETES its row
  (server.py:106) and frees quota, so "4th request in an hour" is only rejected if none of
  the prior three was confirmed. Expired-but-unconfirmed tokens (30-60 min old) still count.
  Count happens before the insert. [Corrected by audit A-01 — the original "3 requests per
  rolling hour" phrasing was falsified by the confirm-refund path.]
  fidelity: FIXED (limit=3, window=3600s over surviving rows, error shape)
  confidence: cited + traced T2 (traces reset-request-004-ratelimited; ratelimit-refund set)
  evidence: ticketd/app/server.py:16-17,84-89,106
- statement: Header `X-Internal-Bypass: 1` (exact string compare) skips the rate-limit check
  entirely. In-code comment: "undocumented bypass header". Unauthenticated — anyone who knows
  the header name bypasses the limit. Intent unknown: internal tool dependency vs. leftover
  backdoor.
  fidelity: ASK — OQ-004 (blocks: none — WO-006 implements parity behind a config flag
  defaulting ON; flags gate review at M2)   confidence: cited
  evidence: ticketd/app/server.py:84
- statement: Token generation is `md5(f"{email}{time.time()}")` hexdigest, stored in
  **plaintext** in `reset_tokens` alongside email and epoch-float timestamp.
  fidelity: REPAIR — PB-002; target: CSPRNG token (`secrets`), stored hashed; presentable
  token appears only in the outbound email. divergence: ED-003   confidence: cited
  evidence: ticketd/app/server.py:90-92, ticketd/db/schema.sql:18-22
- statement: Every request inserts a NEW row — multiple live tokens per email coexist;
  earlier tokens are not invalidated by later requests.
  fidelity: FIXED (concurrent-validity outcome survives the token-mechanism repair)
  confidence: cited   evidence: ticketd/app/server.py:91-92 (no DELETE on issue)
- statement: The token email is sent synchronously in-request after commit
  (`send_mail(email, f"reset token: {token}")`); SMTP failure → 500 with the token row
  already committed and valid.
  fidelity: REPAIR — PB-001; target: dispatch outside the request path. divergence: ED-002
  confidence: cited (sync send), inferred (500-after-commit shape)
  evidence: ticketd/app/server.py:93-94
- statement: Success response is exactly `{"ok": true}`, 200 — the token never appears in the
  HTTP response, only in the email.
  fidelity: FIXED   confidence: cited   evidence: ticketd/app/server.py:95
- statement: [audit A-13] A non-string `email` (e.g. 42) passes the rate-limit check and the
  INSERT (committed), then crashes in send_mail → 500 with the row persisted. A valid-JSON
  non-object body (e.g. `[1]`, `5`) survives `or {}` and crashes on `.get` → 500 (also
  applies to confirm). Both are accidental crash shapes.
  fidelity: FREE — modern: 422 validation error; same sanction class as ED-004 (garbage
  input cleanups, integration-notes.md#sanctioned-deviations). Not exercised by any replay
  trace, so no ED entry is required; adding such a probe requires adding a manifest entry.
  confidence: inferred   evidence: ticketd/app/server.py:82-83,91-94,100-102

## Feature: confirm reset — POST /api/auth/reset/confirm

- statement: Lookup is by token string alone (no email cross-check). Unknown token OR token
  older than 30 minutes → 403 with the **identical** body `{"error":"invalid_token"}` —
  in-code comment marks the non-disclosure deliberate.
  fidelity: FIXED (explicitly deliberate; expiry constant RESET_WINDOW_MIN=30)
  confidence: cited   evidence: ticketd/app/server.py:16,100-105
- statement: Valid token → row(s) with that token DELETED (single-use), commit, then 200
  `{"ok": true, "email": <row.email>}` — the email echo is the flow's only output and the
  only hint of its purpose (OQ-002).
  fidelity: FIXED   confidence: cited   evidence: ticketd/app/server.py:106-108
- statement: Expired rows are never deleted (only filtered at confirm); the table grows
  unboundedly.
  fidelity: FREE — NARROWED by audit A-02: purge only rows with created_ts older than
  3600s. Rows aged 30-60 min are expired for confirm but still count toward the rate limit
  (statement above), so purging them would change observable 429 behavior. Outcomes
  required: expired tokens unusable AND rate-limit counting unaffected.
  confidence: cited   evidence: ticketd/app/server.py:85-88 vs :103 (window mismatch)
