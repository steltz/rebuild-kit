# Legacy `ticketd` audit

Source: contractor handoff at `../ticketd-nohistory` (no git history, no access
logs, no production DB access at time of writing — 2026-08-09). Everything
below is derived from reading the four application files and the schema; none
of it is confirmed against real traffic or data yet.

## What the app is

A Flask 1.x-era service (`app/server.py`) backed by SQLite (`db/ticketd.sqlite3`,
schema in `db/schema.sql`). Three tables: `tickets`, `users` (referenced by
`tickets.assignee_id` but never written to by any route in this codebase —
users must be provisioned some other way), `reset_tokens`.

Six routes:

| Route | Method | Purpose |
|---|---|---|
| `/api/tickets` | GET | List tickets, optional `?status=` filter, no pagination |
| `/api/tickets` | POST | Create a ticket |
| `/api/tickets/<id>` | GET | Fetch one ticket |
| `/api/tickets/<id>/close` | POST | Close a ticket, notifies watchers |
| `/api/auth/reset` | POST | Request a password-reset token |
| `/api/auth/reset/confirm` | POST | Redeem a reset token |
| `/internal/export/csv` | GET | Dump all tickets as CSV |

## Confirmed problems (from handover notes)

1. **Synchronous email inside requests.** `notify.send_mail` opens an SMTP
   connection with a 30s timeout and blocks the request thread. It's called
   from `close_ticket` and `request_reset`. An SMTP outage or slowdown takes
   ticket-closing and password reset down with it (`app/notify.py:1`,
   `app/server.py:76`, `app/server.py:94`).
2. **MD5 reset tokens.** `hashlib.md5(f"{email}{time.time()}")` is used to
   generate the token, and the token is stored in plaintext in
   `reset_tokens.token` (`app/server.py:90`). MD5 is not a secret-token
   generator — it's a hash function being fed low-entropy, partially-guessable
   input (email is public, timestamp is narrow). Storing the plaintext token
   also means a DB read exposes every live reset token.

## Additional things found while reading (not in the handover notes)

These are **not** treated as "known problems to fix" — logged here as findings
because we found them by reading code, not because anyone confirmed they
matter in production. Decisions on each are in `DESIGN.md` /
`OPEN_QUESTIONS.md`.

- **Undocumented rate-limit bypass**: `X-Internal-Bypass: 1` skips the
  reset-rate-limit check entirely, with no authentication on the header
  itself (`app/server.py:84`). Any external caller can send this header and
  bypass rate limiting. This looks like it was meant for internal
  service-to-service calls but as written it's a rate-limit bypass anyone can
  use.
- **`GET /api/tickets/<id>` on a missing ticket returns `200 {}`**, not `404`.
  The comment says "the legacy UI depends on it" (`app/server.py:63`). We have
  no access logs to confirm this, but the comment is explicit enough to
  treat as a real constraint until we can check.
- **Priority accepts `"1"/"2"/"3"` or `"low"/"med"/"high"`**, and the comment
  says both must keep working because clients send both (`app/server.py:47`).
- **Slugs can collide.** `slugify` truncates to 64 chars and does no
  uniqueness check; two titles that normalize the same way (`"Fix DB"` /
  `"fix db!"`) get the same slug (`app/util.py:6`). No unique constraint in
  the schema either.
- **Naive local time.** `datetime.now()` (not `.utcnow()`) is stored as text
  in `created_at`/`closed_at` (`app/server.py:52`, `:71`). Timezone of the
  server process is baked into every timestamp with no offset recorded.
- **`/internal/export/csv`** has a comment saying it was "written for the 2020
  audit; no caller since." May be genuinely dead.
- **`app/legacy_import.py`** is explicitly dead code ("Nothing imports this
  module") — a one-off CSV importer from a 2019 spreadsheet migration.
- **`users` table is never written to** by anything in this codebase. User
  provisioning happens out of band (admin console? direct SQL? unknown).
- Three trailing `# tweak 1/2/3` comments and a stray `# note` in `util.py`
  suggest manual hotfixes with no accompanying commit messages or history —
  consistent with "no git history came with it."

## Scope boundary for this rewrite

Per the handover: the two confirmed problems above are the only *known*
problems, and we're told that's genuinely all that's known. So the rewrite:

- **Fixes** the two confirmed problems.
- **Preserves** every other observed behavior/quirk byte-for-bit where
  practical, because we have no evidence about who depends on what.
- **Documents** everything else found above as open questions to resolve once
  access logs / production DB access exist (expected "in a few weeks" per the
  handover).
- **Does not port** `legacy_import.py` — it's explicitly dead, one-off, and
  porting unused code forward would be scope creep with no evidence anyone
  needs it. If the evidence-gathering phase turns up a live caller, it's a
  small, isolated addition later.
