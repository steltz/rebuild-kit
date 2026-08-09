# Entity: ResetToken

Table `reset_tokens` (`ticketd/db/schema.sql:18-22`). A bare table: no PK, no unique
constraint, no index, no FK to `users` — any email string can request a token, registered
or not (`app/server.py:82-95` never consults `users`).

| field | type | notes / enforcement site |
|---|---|---|
| email | TEXT NOT NULL | requester-supplied, unvalidated (`app/server.py:83`); empty string allowed |
| token | TEXT NOT NULL | `md5(email + time.time())` hex, stored **cleartext** (`app/server.py:90-92`) — PB-002 |
| created_ts | REAL NOT NULL | epoch seconds UTC, `time.time()` (`app/server.py:92`) |

## Lifecycle

- **Issue** (`POST /api/auth/reset`): rate limit — ≥3 tokens for the same email within the
  trailing 3600s → 429 (`app/server.py:85-89`, constants `app/server.py:16-17`), unless
  header `X-Internal-Bypass: 1` (`app/server.py:84`, OQ-002). Insert + synchronous email
  containing the raw token (`app/server.py:91-94`, PB-001).
  Note: bypassed requests still insert rows, so they **count toward** later non-bypassed
  rate-limit checks (`app/server.py:85-88` counts all rows).
- **Confirm** (`POST /api/auth/reset/confirm`): look up by token; missing OR older than 30
  minutes → 403 `{"error":"invalid_token"}` — deliberately the same body for both causes
  (non-disclosure, `app/server.py:103-105` and its comment). Valid → delete that token row
  (single-use, `app/server.py:106`) → 200 `{ok: true, email}`.
- **Expiry**: check-on-read only. Expired rows are never deleted (DNP-003).
- Multiple live tokens per email are allowed; each is independently confirmable.

## Invariants

- I1: single-use — DELETE on successful confirm (`app/server.py:106`). Race window exists
  (SELECT then DELETE, no transaction guard) — two concurrent confirms of the same token
  could both succeed on some interleavings; not observed, noted for the modern design.
- I2: 30-minute validity — enforced at confirm (`app/server.py:103`, `RESET_WINDOW_MIN`
  `app/server.py:16`).
- NOT enforced: email validity, email existence in `users`, one-live-token-per-email.
