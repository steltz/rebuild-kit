# Draft spec — auth-reset/request  (`POST /api/auth/reset`)

Usage weight 0.0195. Perf p50 92ms / p95 212ms / p99 306ms. Churn hotspot: 3 of 4 legacy
commits are reset-flow hotfixes (`hotspots.md`).

| id | claim | fidelity | confidence | evidence |
|---|---|---|---|---|
| RR-1 | Body JSON, `email` defaulting to `""`; no validation, no existence check against `users`; empty email is accepted and rate-limited under key `""` | FIXED | cited+traced | `ticketd/app/server.py:82-83`; trace `auth-reset-req-006`. **Audit caveat (AD-005):** the 200 for empty email is observed under the harness mail sink; in prod, a real SMTP server may refuse recipient `""` → unhandled exception → 500 *after* the insert. Unverifiable without prod SMTP behavior (no 5xx on this route in the 30-day log). Moot post-repair: with dispatch decoupled (ED-003), modern returns 200 regardless and the worker owns delivery failures |
| RR-2 | Rate limit: if ≥3 tokens for this email in trailing 3600s → 429 `{"error":"rate_limited"}`, nothing inserted, no email | FIXED | cited+traced | `ticketd/app/server.py:16-17,85-89`; traces `auth-reset-req-001..004` |
| RR-3 | Header `X-Internal-Bypass: 1` (exact string) skips the rate-limit check entirely | ASK (OQ-002) — frozen as-is pending ruling | cited+traced | `ticketd/app/server.py:84` ("undocumented bypass header"); trace `auth-reset-req-005` |
| RR-4 | Bypassed requests still INSERT rows, so they count toward subsequent non-bypassed checks | FIXED (consequence of RR-3 freeze) | cited+traced | `ticketd/app/server.py:85-92` (count is over all rows); trace `auth-reset-req-005` then `-007` |
| RR-5 | Token = `md5(f"{email}{time.time()}")` hexdigest, stored cleartext in `reset_tokens` | REPAIR (PB-002) → target: ≥128-bit random token, hashed at rest; single-use + 30-min expiry preserved. Divergence ED-002 | cited+traced | `ticketd/app/server.py:90-92`; trace `auth-reset-req-001` state.token_store |
| RR-6 | Reset email sent synchronously in-request, body `reset token: <token>` to the requester address | REPAIR (PB-001, sync part) → dispatch decoupled, ED-003; body/recipient outcome FIXED except token format (follows RR-5's repair) | cited+traced | `ticketd/app/server.py:94`, `ticketd/app/notify.py:5-7`; trace `auth-reset-req-001` state.email |
| RR-7 | Success response 200 `{"ok": true}` — token never in the response | FIXED | cited+traced | `ticketd/app/server.py:95`; trace `auth-reset-req-001` |
| RR-8 | Multiple live tokens per email allowed (each request inserts another row) | FIXED | cited+traced | `ticketd/app/server.py:91-92` (no upsert); traces `auth-reset-req-002/003` |
