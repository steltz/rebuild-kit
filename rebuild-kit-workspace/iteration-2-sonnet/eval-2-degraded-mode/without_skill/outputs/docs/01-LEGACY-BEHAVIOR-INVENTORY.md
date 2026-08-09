# Legacy Behavior Inventory (ticketd)

Extracted by reading `./ticketd` line by line. Source refs are
`file:line` against the handed-over tree. Nothing here is inferred from
outside the code.

## Stack as found

- Flask 1.x era app (`ticketd/app/server.py:1`), single process, `sqlite3`
  standard-library driver, `app.run(port=5000)` — no WSGI server config
  visible, so unknown how it's actually deployed/fronted in production.
- Data store: SQLite file `db/ticketd.sqlite3` (`server.py:14`), schema in
  `db/schema.sql`.
- Outbound email via raw `smtplib` to `smtp.internal:25` (`app/notify.py`).

## Endpoints

| Method | Path | Source | Notes |
|---|---|---|---|
| GET | `/api/tickets` | `server.py:27-37` | Optional `?status=` filter. **No pagination** — comment says the UI fetches everything and filters client-side. Orders by `created_at DESC`. |
| POST | `/api/tickets` | `server.py:40-55` | Requires non-empty `title` (whitespace-trimmed) or 422 `title_required`. `priority` accepts **either** the strings `low`/`med`/`high` **or** the strings `"1"`/`"2"`/`"3"` (mapped 1→low, 2→med, 3→high) — comment says both forms are actively sent by clients. New tickets always `status='open'`. Returns `201` with `{id, slug}`. |
| GET | `/api/tickets/<id>` | `server.py:58-64` | **Returns HTTP 200 with `{}`** for a ticket that doesn't exist — not 404. Comment: "historical quirk ... the legacy UI depends on it." |
| POST | `/api/tickets/<id>/close` | `server.py:67-77` | Idempotent-ish: only flips status if not already closed (`AND status != 'closed'`); returns `{closed: bool}`. **Sends a notification email synchronously in-request** on success — this is Known Problem #1. |
| POST | `/api/auth/reset` | `server.py:80-95` | Rate-limited to 3 requests/hour per email (`RATE_LIMIT_PER_HOUR`), **except** when header `X-Internal-Bypass: 1` is present — this bypass is undocumented anywhere outside this one `if`. Token is `md5(email + time.time())` — Known Problem #2. Also sends synchronously (same problem as above, same fix). |
| POST | `/api/auth/reset/confirm` | `server.py:98-108` | Token must exist and be younger than `RESET_WINDOW_MIN` (30) minutes. Expired and invalid tokens return the **identical** `403 {"error": "invalid_token"}` body — deliberate non-disclosure per inline comment; must be preserved for parity, not "fixed" into distinguishing error messages. |
| GET | `/internal/export/csv` | `server.py:111-115` | Full unfiltered dump as CSV (`id,title,status` only — priority/assignee/dates not exported). Comment: "written for the 2020 audit; no caller since." Unauthenticated in the code as written. |

## Schema as found (`db/schema.sql`)

- `tickets(id, title, slug, priority CHECK low/med/high, status CHECK open/closed, assignee_id -> users.id, created_at, closed_at)`
- `users(id, email UNIQUE, name)`
- `reset_tokens(email, token, created_ts)` — no primary key, no index, no
  foreign key to `users`; `email` is a free string here, not validated
  against `users.email`.

## Known Problems (named in handover — authoritative)

1. **Synchronous notification email inside the request path**
   (`server.py:76`, `server.py:94`, implemented in `app/notify.py`).
   `notify.py`'s own docstring says "~2s typical, 30s on provider trouble" —
   an SMTP outage or slowdown directly stalls `close_ticket` and
   `request_reset` responses.
2. **Password-reset tokens are MD5** (`server.py:90`):
   `hashlib.md5(f"{email}{time.time()}").hexdigest()`. Predictable/brute-forceable
   and not a credential a password-reset system should be minting.

## Other things noticed while reading (NOT in handover — unconfirmed, not fixed)

These are static-analysis observations, not confirmed production issues. They
are preserved as-is in the rewrite and listed here + in the risk register so
they aren't lost, but none were "known problems" per the handover and none
were fixed without evidence:

- `util.py:5` — `slugify()` can collide ("Fix DB" and "fix db!" both slugify
  to `fix-db`); schema has no uniqueness constraint on `slug`.
- `server.py:52` — ticket `created_at` uses `datetime.now()` (naive local
  time, no timezone), flagged by the original author's own comment.
- `server.py:84` — the `X-Internal-Bypass` rate-limit bypass header has no
  authentication of its own (any caller can send the literal string `1`).
- No pagination on `GET /api/tickets` (see table above) — fine at unknown
  current scale, unknown at future scale.
- `reset_tokens` table is never pruned — expired/used tokens (the latter are
  deleted on confirm, `server.py:106`, but *unused* expired ones are not)
  accumulate forever.
- `legacy_import.py` — docstring says "nothing imports this module"; excluded
  from the rewrite's runtime path, kept only as a historical reference for
  whoever eventually does the one-time data migration.
- Trailing `# tweak 1` / `# tweak 2` / `# tweak 3` comments at the end of
  `server.py` with no accompanying code — no git history to explain what they
  refer to.
