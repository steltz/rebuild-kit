# ticketd: Current Behavior Contract (reverse-engineered from source)

**Purpose:** This is the authoritative record of what `ticketd` (Flask + SQLite,
`ticketd/app/server.py`) actually does today, including its bugs and quirks.

Because this is a backend-only rewrite (**no UI changes**), the existing frontend
(`svc-ui/2.1`, per the access log) is the ultimate compatibility target. Every
quirk documented here is either:

- **[PRESERVE]** — the frontend or another consumer is known or assumed to depend
  on this exact behavior; the rewrite must replicate it byte-for-byte, or
- **[FIX]** — a bug we are intentionally correcting as part of this rewrite
  (must be listed in `00-CONTEXT-AND-CONSTRAINTS.md` scope), or
- **[OPEN]** — unclear whether it's load-bearing; see `03-OPEN-QUESTIONS.md`.

Source read in full: `ticketd/app/server.py`, `ticketd/app/notify.py`,
`ticketd/app/util.py`, `ticketd/app/legacy_import.py`, `ticketd/db/schema.sql`,
`ticketd/README.md`. There is no test suite and no OpenAPI/Swagger doc in the
legacy repo — this document is the closest thing to a spec that exists, and it
was built entirely by reading the code, so treat every `[OPEN]` item as a real
gap, not false modesty.

## 1. Data model (SQLite, `db/schema.sql`)

```sql
CREATE TABLE tickets (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    priority TEXT CHECK (priority IN ('low', 'med', 'high')),
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    assignee_id INTEGER REFERENCES users(id),
    created_at DATETIME NOT NULL,
    closed_at DATETIME
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE reset_tokens (
    email TEXT NOT NULL,
    token TEXT NOT NULL,
    created_ts REAL NOT NULL
);
```

Notes:
- `slug` has **no uniqueness constraint** at all today. This is the root cause
  of the collision bug support keeps hitting — see `util.slugify`.
- `assignee_id` exists in the schema but **no endpoint reads or writes it**.
  There is no evidence in the code or the access log that assignment is a live
  feature. [OPEN] — see open questions.
- `reset_tokens` has no primary key, no index, and no expiry/used columns —
  expiry is computed at read time from `created_ts`, and "used" is enforced by
  `DELETE`-on-confirm (row is gone after one use).
- `users` table exists but nothing in `server.py` reads from it — reset
  requests accept any `email` string with no check it belongs to a real user.
  [OPEN]

## 2. Endpoints

All bodies are JSON. All responses are JSON except the CSV export.

### `GET /api/tickets`
- Query param `status` (optional) — exact match filter, values are whatever
  the DB has (`open`/`closed` by schema, unvalidated).
- **No pagination.** Comment in code: *"the UI relies on getting everything
  and filtering client-side."* **[PRESERVE-CRITICAL]** — this is the single
  highest-traffic endpoint (62% of all requests in the sample log). Removing
  pagination support without a client change would break the UI, and UI
  changes are out of scope. The rewrite may *add* optional pagination
  parameters as long as omitting them returns the full unpaginated list in
  the same shape as today.
- Ordered by `created_at DESC`.
- Returns `200` with a JSON array of ticket objects (`SELECT *` shape — i.e.
  every DB column, including `assignee_id` even though nothing sets it).

### `POST /api/tickets`
- Body: `{"title": str, "priority": str|int}` (both optional-ish — see below).
- `title` — required, whitespace-stripped; empty/missing → `422
  {"error": "title_required"}`.
- `priority` — **accepts both integer-as-string and word form**. Comment:
  *"clients send both, both must keep working."* Mapping: `"1"→"low"`,
  `"2"→"med"`, `"3"→"high"`. Anything else is passed through **unvalidated**
  to the SQL insert. Default when omitted: `"med"`.
  - **[FIX] Bug:** if a caller sends a `priority` value outside
    `{1,2,3,low,med,high}` (e.g. `"urgent"`), the DB `CHECK` constraint raises
    a `sqlite3.IntegrityError` that Flask does not catch → **uncaught 500**.
    The access log confirms unhandled 500s exist on `POST /api/tickets`
    (2.55% of all requests are 500s across the sampled window). The rewrite
    should validate `priority` against the allowed set and return a proper
    `422` instead of a `500`. This changes a status code from 500→422 for
    malformed input only; it does not change any *valid* request's behavior,
    and 500s were never a documented/intentional contract.
- `slug` is derived from `title` via `slugify()` (see §4) and stored — **no
  collision handling of any kind today.**
- `status` is hardcoded to `'open'` on creation.
- `created_at` — `datetime.now().isoformat()`, **naive local server time**
  (comment in code: `# naive local time!`). **[FIX, but see open question]**
  — see §5.
- Response: `201 {"id": <int>, "slug": <str>}`.
  - **Bug note:** the response recomputes `slugify(title)` independently
    from what was actually inserted — today these always match because both
    calls are deterministic on the same `title`, so this is not currently
    observable, but if slug-collision suffixing is added, the response MUST
    return the slug that was actually persisted, not a fresh `slugify(title)`
    call. This is a concrete trap for the rewrite to avoid.

### `GET /api/tickets/<int:id>`
- **[PRESERVE-CRITICAL]** — if no row matches, returns **`200 {}`**, not
  `404`. Comment: *"historical quirk ... the legacy UI depends on it."* The
  rewrite MUST return `200` with an empty JSON object for unknown ticket ids,
  not a `404`. This is the single quirk most likely to break the UI silently
  if "cleaned up" during the rewrite — flagging it here explicitly because it
  looks like an obvious bug to fix and is not one we're allowed to fix.
- Otherwise `200` with the full ticket row.

### `POST /api/tickets/<int:id>/close`
- Idempotent-ish: `UPDATE ... WHERE id = ? AND status != 'closed'`. If the
  ticket was already closed (or doesn't exist), `rowcount` is 0.
- Sets `closed_at = datetime.now().isoformat()` (same naive-local-time issue).
- Response: `200 {"closed": bool}` — `true` only if this call actually
  transitioned the ticket, `false` if already closed or id unknown (note:
  unlike `GET`, an unknown id here does *not* get the `200 {}` treatment — it
  just returns `{"closed": false}`, same as an already-closed ticket. The
  rewrite should preserve this: do not distinguish "not found" from "already
  closed" in the response.)
- **This is the endpoint from the June incident.** On success it calls
  `send_mail()` **synchronously, inside the request**, with a 30s SMTP
  socket timeout (`app/notify.py`). When the SMTP provider is down or slow,
  every close request blocks for up to 30s and ties up a worker thread; at
  sustained close volume this exhausts the app's request-handling capacity,
  which is what took ticket-closing down for 40 minutes. **This is the
  primary driver for the rewrite. [FIX — top priority]**
- **[OPEN]** Today, if `send_mail()` raises (SMTP down, DNS failure, etc.),
  the exception is uncaught — the whole request 500s **even though the
  ticket was already committed as closed** (the `db().commit()` happens
  before `send_mail()` is called). So today's failure mode is: ticket *is*
  closed, client sees a `500`, no email goes out, and the client likely
  retries (hitting the now-idempotent `changed=0` path, which returns
  `200 {"closed": false}` — a confusing "did it work?" state). Any async
  design should be a strict improvement on this, not just as fast.

### `POST /api/auth/reset`
- Body: `{"email": str}`.
- Rate limit: max `RATE_LIMIT_PER_HOUR = 3` reset requests per email per
  rolling hour, **unless** the request has header `X-Internal-Bypass: 1`.
  - **[OPEN — security-relevant]** This header is undocumented (no comment
    explaining who sets it or why) and completely bypasses rate limiting with
    no other authentication. See open questions — this needs a decision
    before the rewrite ships, not an assumption.
  - Over limit → `429 {"error": "rate_limited"}`.
- Token generation: `hashlib.md5(f"{email}{time.time()}").hexdigest()`.
  **[FIX — security, explicitly flagged by security team.]** This is weak in
  two independent ways: (1) MD5 is used, and (2) more importantly, the token
  *is* derived deterministically from low-entropy, partially-public inputs
  (the email address and a timestamp that's guessable to within the request's
  RTT) rather than being a securely random secret that MD5 merely hashes.
  Given the email and an approximate request time, the token space is small
  enough to brute-force offline. See `DESIGN-password-reset.md`
  for the fix.
- Token stored **in plaintext** in `reset_tokens` (bare table, no expiry
  column — expiry is computed at read time).
- Always sends the token by email (`send_mail`, also synchronous — same
  outage risk as ticket-close, lower volume today but same class of bug).
- Response: `200 {"ok": true}` in all non-rate-limited cases (note: this
  responds `ok: true` even if the email doesn't correspond to a real user,
  since `email` is never validated against `users`. This is actually a
  *good* anti-enumeration property — preserve it).

### `POST /api/auth/reset/confirm`
- Body: `{"token": str}`.
- Looks up the token; if not found **or** older than
  `RESET_WINDOW_MIN = 30` minutes → `403 {"error": "invalid_token"}`.
  **[PRESERVE-CRITICAL]** — comment: *"deliberate: expired and invalid
  tokens return the SAME body (non-disclosure)."* The rewrite's new
  token-hashing scheme must preserve this exact non-disclosure property:
  expired, already-used, and never-issued tokens must all be
  indistinguishable `403 {"error": "invalid_token"}` responses.
- On success: deletes the token row (single-use), returns
  `200 {"ok": true, "email": <str>}`.

### `GET /internal/export/csv`
- Dumps `id,title,status` for all tickets as CSV.
- Comment: *"written for the 2020 audit; no caller since."* Confirmed by the
  access log — **zero requests to this path** across the sampled window
  (2,000 requests, only 6 distinct routes seen, this isn't one of them).
  [OPEN] — candidate to drop; see open questions. Cheap to keep either way.

### `app/legacy_import.py`
- `import_spreadsheet(path)` — one-off CSV importer from the 2019 spreadsheet
  migration. Comment: *"Nothing imports this module."* Confirmed by
  inspection — unused, dead code. **Do not port this.** Note its existence
  in the rewrite history/README for institutional memory only.

## 3. Auth / identity

There is **no authentication or authorization anywhere in this API.** Every
endpoint is open. The access log shows a single caller identity
(`jdoe@corp.example.com` in the user field, `svc-ui/2.1` user agent) for
100% of the sampled traffic, which looks like the log is annotating requests
with an upstream-authenticated identity (e.g. from a gateway/proxy) rather
than `ticketd` doing its own auth. **[OPEN — important]**: confirm whether
`ticketd` sits behind an authenticating reverse proxy / gateway in production
that this rewrite must continue to assume, or whether the log is a synthetic
single-user sample and real traffic has multiple identities. The rewrite as
scoped **does not add authentication** (that would be a scope increase no one
asked for) but the plan should not accidentally make an assumption that
breaks whatever fronts this service today.

## 4. `slugify()` (`app/util.py`)

```python
def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64]
```

Lossy and collision-prone by construction: `"Fix DB"` and `"fix db!"` both
slugify to `"fix-db"`. No uniqueness is enforced anywhere (schema has no
unique index on `slug`), so two tickets can and do end up with the same slug.
This is one of the three named problems this rewrite must fix — see
`DESIGN-slug-collisions.md`.

## 5. Timestamps

Every timestamp (`created_at`, `closed_at`, reset-token `created_ts`) is
generated with naive local server time (`datetime.now()` / `time.time()`),
not UTC, and serialized without a timezone offset. This is a real bug — but
fixing it changes the literal timestamp *strings* the API returns, which the
UI renders. Since UI changes are out of scope, this needs an explicit call on
whether "change what timestamps look like on the wire" counts as a UI change.
Default assumption used in the plan (flagged in `03-OPEN-QUESTIONS.md`):
**store timestamps correctly as UTC internally (Postgres `timestamptz`), but
do not change the API's serialized format** — see the design doc for the
exact approach.

## 6. What the access log tells us about real traffic (see `04-TRAFFIC-ANALYSIS.md` for full detail)

- 2,000 requests, single sampled window, single client (`svc-ui/2.1`),
  single identity (`jdoe@corp.example.com`).
- Read-heavy: `GET /api/tickets` is 61.75% of all traffic.
- Status codes: 1948×200, 51×500, 1×429. The 500s are unexplained in the log
  itself (no error body) but are fully explained by the `priority`
  CHECK-constraint bug above.
- No requests to `/internal/export/csv` at all.
