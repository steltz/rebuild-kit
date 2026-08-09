# Draft spec — auth-reset/confirm  (`POST /api/auth/reset/confirm`)

Usage weight 0.01 (lowest live route). Perf p50 119ms / p95 301ms.

| id | claim | fidelity | confidence | evidence |
|---|---|---|---|---|
| RC-1 | Body JSON, `token` defaulting to `""`; lookup by exact token string | FIXED (lookup semantics move to hashed compare under PB-002 — outcome identical) | cited+traced | `ticketd/app/server.py:100-102`; trace `auth-reset-confirm-001` |
| RC-2 | Unknown token → 403 `{"error":"invalid_token"}` | FIXED | cited+traced | `ticketd/app/server.py:103-105`; trace `auth-reset-confirm-003` |
| RC-3 | Expired token (age > 30min, `RESET_WINDOW_MIN`) → **the same** 403 body as unknown — deliberate non-disclosure; do not differentiate | FIXED | cited | `ticketd/app/server.py:103-105` + comment "deliberate: expired and invalid tokens return the SAME body". No trace (would need clock control; covered by modern characterization test with injected clock — `verification/characterization/test_auth_reset.py::test_expired_token_same_body`) |
| RC-4 | Expired tokens are NOT deleted on failed confirm — they just fail | FIXED behavior at the API; storage-side accumulation is DNP-003 (modern store may purge; API-visible behavior must not change) | cited | `ticketd/app/server.py:103-106` (delete only on success path) |
| RC-5 | Valid token: delete that token row (single-use), 200 `{"ok": true, "email": <email>}` | FIXED | cited+traced | `ticketd/app/server.py:106-108`; traces `auth-reset-confirm-001/002` (002 = replay same token → 403) |
| RC-6 | Confirm has no rate limit and no bypass logic | FIXED | cited | `ticketd/app/server.py:98-108` (absent) |
| RC-7 | What the returned `email` is *for* is unknown — no password store exists | ASK (OQ-006) — implement the observable contract exactly | inferred | `ticketd/db/schema.sql:12-16` (no password column); no consumer in repo |

Concurrency note (informational, for modern design): legacy SELECT-then-DELETE is not
atomic (`ticketd/app/server.py:101-106`); modern single-use enforcement should be atomic
(DELETE ... RETURNING) — same observable behavior, stronger guarantee; not a divergence.
