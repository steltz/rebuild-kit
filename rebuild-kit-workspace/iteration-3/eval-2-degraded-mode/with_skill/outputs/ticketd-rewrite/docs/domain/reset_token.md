# Entity: Reset Token

## Fields
(source: `legacy/db/schema.sql:18-22`, cross-checked against `legacy/app/server.py:80-108`)

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `email` | TEXT | NOT NULL | Not validated as a well-formed email address anywhere in the tree — whatever string the client sends is stored and mailed to as-is (legacy/app/server.py:83, 94). |
| `token` | TEXT | NOT NULL | `hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()` (legacy/app/server.py:90) — **PB-002**. **No UNIQUE constraint in the schema** — nothing in the DB prevents two rows with the same token; collision resistance is entirely delegated to MD5's output space and the low probability of two requests landing the same wall-clock `time.time()` float for the same email. |
| `created_ts` | REAL | NOT NULL | `time.time()` (Unix epoch seconds), used both for the 1-hour rate-limit window (legacy/app/server.py:87) and the 30-minute redemption window (legacy/app/server.py:103). |

**No primary key at all** on `reset_tokens` (legacy/db/schema.sql:18-22) — every row is
independently insertable, including exact duplicates. This is worth carrying into the rewrite's
schema design as a FREE choice (Postgres will want a real PK), not a FIXED behavior to replicate
literally (a missing PK is not an externally observable API behavior).

## Lifecycle

```
(none) --request(rate-limited)--> issued --confirm(within 30 min, single-use)--> (deleted)
                                       |
                                       +--expired (>30 min, never confirmed)--> (row lingers; no
                                                                                  reap job found)
```
- Issue: `POST /api/auth/reset` (legacy/app/server.py:80-95). Rate-limited to 3 requests/hour
  per email (legacy/app/server.py:85-89), bypassable via `X-Internal-Bypass: 1`
  (legacy/app/server.py:84 — `docs/open-questions.md#OQ-001`).
- Redeem: `POST /api/auth/reset/confirm` (legacy/app/server.py:98-108). Deletes the row on
  success (legacy/app/server.py:106) — single-use, enforced by deletion, not by a `used` flag.
- Expiry: checked at redemption time only (`time.time() - row["created_ts"] > 1800`,
  legacy/app/server.py:103); **no background reaper** exists in the tree, so expired-and-never-
  redeemed rows accumulate indefinitely. Not in the problem brief; noted as an NFR candidate for
  the rewrite's FREE token-storage mechanism, not a REPAIR (no PB citation).

## Invariants

- Expired and invalid tokens return the **identical** error body/status
  (`403 {"error": "invalid_token"}`, legacy/app/server.py:103-105) — deliberate non-disclosure,
  explicitly commented as such. FIXED; this is the one security property of the legacy flow that
  is *working as intended* and must be preserved, even while PB-002 replaces the token generation
  mechanism underneath it.
- Rate limit is per-`email` string, not per-requester/IP, and is skippable by anyone who sends
  the bypass header (no auth on it) — see OQ-001 for whether that's intended.
