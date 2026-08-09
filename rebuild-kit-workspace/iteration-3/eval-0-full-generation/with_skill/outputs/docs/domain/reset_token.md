# Entity: Reset Token

Table: `reset_tokens` (`ticketd/db/schema.sql:18-22`). Owned by the Auth/Reset subsystem. This is
the entity at the center of PB-002.

## Fields

| field | type (legacy) | nullable | notes |
|---|---|---|---|
| `email` | `TEXT NOT NULL` | no | Not validated as a real email address anywhere (`server.py:83`: `body.get("email", "")`, empty string is a legal value — an empty-email reset request is accepted and even rate-limited/tokenized like any other, `server.py:85-95`). Not a FK to `users.email` — the reset flow is entirely decoupled from the `users` table (no route ever looks a user up before issuing a token). |
| `token` | `TEXT NOT NULL` | no | `hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()` (`server.py:90`) — deterministic given email+timestamp, no cryptographic randomness, MD5 (broken as a security primitive; also not what it's being used for here — this is really "generate an unguessable bearer credential," which MD5-of-low-entropy-input does not provide). This is PB-002's core defect. |
| `created_ts` | `REAL NOT NULL` | no | `time.time()` (Unix epoch float) — used both as the rate-limit window anchor (`server.py:86-87`) and the expiry check (`server.py:103`). No timezone ambiguity here (epoch time is unambiguous), unlike `tickets.created_at`. **P9 audit note**: `server.py:90` (inside the token expression) and `server.py:92` (the `INSERT`'s `created_ts` value) each call `time.time()` independently — the timestamp embedded in the MD5 hash input and the stored `created_ts` column are two distinct clock reads, not one shared value, differing by whatever microseconds elapse between the two calls. This has no behavioral consequence for any currently-documented claim (the token is never reconstructed from `created_ts`), but WO-003's replacement design should not assume the two ever shared a single timestamp source if it inherits any of this reasoning. |

No primary key, no index on `email` or `token` (`schema.sql:18-22` declares no `PRIMARY KEY`,
`UNIQUE`, or index at all) — every query against this table (`server.py:86-87`, `:101-102`) is a
full table scan. Not flagged as a perf problem in the brief, but worth carrying into the Postgres
DDL as an obvious `email` + `token` index addition (FREE — outcome unaffected, purely a
performance improvement with no behavior change, doesn't need a PB entry).

## Lifecycle

```
(request_reset: insert) -> pending -> (confirm_reset: success) -> deleted
                                    -> (confirm_reset: expired/invalid) -> stays pending forever
```

**There is no expiry sweep.** A token that is never confirmed (abandoned flow, or blocked by rate
limiting on a later attempt) stays in the table indefinitely — the 30-minute expiry
(`RESET_WINDOW_MIN`, `server.py:16`) is enforced only at *read* time in `confirm_reset()`
(`server.py:103`), not by any deletion job. This is part of what PB-002 means by "bare table":
unbounded growth, no cleanup, in addition to the weak hash. The rewrite's expiry-based cleanup
requirement (PB-002 disposition) needs to add what's missing here, not just swap the hash
algorithm.

## Invariants

- **Tokens are single-use** — enforced by `DELETE FROM reset_tokens WHERE token = ?` immediately
  after a successful confirm (`server.py:106`), inside the same handler, before commit
  (`server.py:106-107`). FIXED, evidenced, straightforward to preserve.
- **Tokens expire after 30 minutes** (`RESET_WINDOW_MIN = 30`, `server.py:16`) — enforced at
  confirm-time only (see lifecycle note above; not proactively swept). FIXED as an outcome; the
  *mechanism* (check-on-read vs. a real expiry/TTL at the storage layer) is FREE.
  - Deliberate design choice, evidenced by an in-line comment: expired and invalid (not-found)
    tokens return the **identical** error body and status (`{"error": "invalid_token"}`, `403`) —
    "deliberate: expired and invalid tokens return the SAME body (non-disclosure)"
    (`server.py:103-105`). This is a security-conscious behavior, not a bug — FIXED, must be
    preserved exactly, including in whatever new token mechanism WO-003 builds.
- **Rate limit: 3 requests/hour per email** — enforced by counting rows with matching `email` and
  `created_ts` within the last hour (`server.py:85-88`), **unless** the request carries header
  `X-Internal-Bypass: 1` (`server.py:84`), which skips the check entirely. The limit itself is
  FIXED; the bypass mechanism's fate is PB-008/OQ-002 (undecided).
- **No relationship to the `users` table** — a reset can be requested for any email string,
  registered or not, and the response (`{"ok": true}`, `server.py:95`) does not disclose whether
  the email exists (a real, if perhaps accidental, security-conscious property — worth explicitly
  preserving, not just as a side effect of the code being simple). Same non-disclosure pattern as
  the expired/invalid confirm response; flagged here so the rewrite doesn't accidentally add an
  "email not found" branch that leaks user existence.
