# Entity: ResetToken

## Fields (from `legacy/db/schema.sql:18-22` + `legacy/app/server.py`)

| Field | Type | Notes |
|---|---|---|
| `email` | `TEXT NOT NULL` | not validated as an email shape anywhere; whatever string the client sends is stored and mailed to (`server.py:83,94`) |
| `token` | `TEXT NOT NULL` | `hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()` — **PB-002**. No uniqueness constraint in the schema (no PK, no unique index at all — `db/schema.sql:18-22`) |
| `created_ts` | `REAL NOT NULL` | `time.time()` (unix epoch seconds), used both for the rate-limit window and the expiry check |

No primary key. No index on `email` or `token`. Every query against this table
(`server.py:86-87` rate-limit count, `server.py:101-102` token lookup) is a full table scan at
the sqlite layer today; noted for the Postgres DDL (P5) but not a problem-brief item (no PB
reports it as a performance issue) — addressed as an idiomatic FREE choice (add indexes) since
adding an index changes no observable behavior.

## Lifecycle

```
(POST /api/auth/reset) --insert--> pending --consumed or expired--> gone
```

- Created on `POST /api/auth/reset` (`server.py:90-93`), one row per request — **no dedup**: a
  client can request multiple tokens for the same email; all remain valid until used or expired.
- Consumed: `DELETE FROM reset_tokens WHERE token = ?` on successful confirm (`server.py:106`) —
  single-use, enforced by deletion, not a `used` flag.
- Expired: not deleted proactively (no cleanup job/cron found anywhere in `legacy/` — the table
  grows unboundedly with stale rows); checked reactively at confirm time only
  (`server.py:103`, `RESET_WINDOW_MIN = 30`).

## Invariants

- **Enforced (application code, `server.py:103-105`)**: a token older than 30 minutes
  (`RESET_WINDOW_MIN * 60` seconds) is treated as invalid.
- **Enforced (application code, `server.py:104-105`)**: expired and simply-nonexistent tokens
  return the **identical** response — `403 {"error": "invalid_token"}` — a deliberate
  non-disclosure choice per the inline comment. FIXED, high-confidence (explicit comment,
  behavior is simple and unambiguous in code).
- **Enforced (application code, `server.py:88-89`)**: rate limit of `RATE_LIMIT_PER_HOUR = 3`
  reset requests per email per rolling hour (`created_ts > now - 3600`) — **unless** the request
  carries header `X-Internal-Bypass: 1` (`server.py:84`), which skips the rate-limit check
  entirely. This header is undocumented anywhere else in the codebase. See PB-proposal OQ-004.
- **NOT enforced**: no limit on total outstanding tokens per email, no cleanup of expired rows.

## Security note (context for PB-002, not a new PB — no testimony backs expanding scope)

Because there is no unique/primary key on `reset_tokens`, and `token` is generated from
`email + wall-clock time` (low entropy, no secret material), the MD5 choice (PB-002) is
compounded by the schema offering no defense-in-depth (e.g. no uniqueness enforcement that would
at least reject a colliding token outright). This is included as supporting evidence for WO-001's
risk score, not as an additional problem-brief entry.
