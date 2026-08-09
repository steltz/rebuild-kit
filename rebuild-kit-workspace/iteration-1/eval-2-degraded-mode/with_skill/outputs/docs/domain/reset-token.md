# Entity: ResetToken

Table `reset_tokens` (`ticketd/db/schema.sql:18-22`). No PK, no index, no constraints beyond
NOT NULL — multiple live tokens per email are possible and normal (each request inserts a row,
`app/server.py:91-92`).

## Fields
| field | type | source | notes |
|---|---|---|---|
| email | TEXT NOT NULL | schema.sql:19 | never validated against `users.email` — resets can be requested for ANY address, including unknown ones (`app/server.py:82-95` has no user lookup) |
| token | TEXT NOT NULL | schema.sql:20 | `md5(email + time.time())` hex, stored in plaintext (`app/server.py:90`) — PB-002 |
| created_ts | REAL NOT NULL | schema.sql:21 | unix epoch float (`app/server.py:92`) |

## Lifecycle
```
issued --confirm within 30 min--> consumed (row DELETED, app/server.py:106)
issued --30 min elapse--> expired (row REMAINS; only filtered at read, app/server.py:103)
```
- Expiry window: `RESET_WINDOW_MIN = 30` (`app/server.py:16`), checked only at confirm time.
- Expired rows are **never purged** — the table grows forever; production row count unknown
  until census (OQ-INT-2). Migration must decide what to carry (see docs/migration/mapping.md).

## Invariants (enforcement-cited)
- Single-use: enforced by DELETE-on-confirm (`app/server.py:106`). FIXED outcome.
- 30-minute validity: enforced at confirm (`app/server.py:103`). FIXED outcome.
- Non-disclosure: expired and invalid tokens return the **same** 403 body
  `{"error":"invalid_token"}` — in-code comment marks this deliberate (`app/server.py:104-105`).
  FIXED.
- Rate limit: max 3 issues per email per rolling hour, counted from the table itself
  (`app/server.py:85-89`), skipped when header `X-Internal-Bypass: 1` (`app/server.py:84`) —
  bypass intent unknown → OQ-004.
- Token mechanism (MD5, plaintext at rest): PB-002 → REPAIR; the three outcomes above survive,
  the mechanism does not.
