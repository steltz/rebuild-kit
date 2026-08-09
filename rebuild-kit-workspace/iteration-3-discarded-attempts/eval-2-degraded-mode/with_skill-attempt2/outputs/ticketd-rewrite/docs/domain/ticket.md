# Entity: Ticket

## Fields (from `legacy/db/schema.sql:1-10` + `legacy/app/server.py`)

| Field | Type | Notes |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | sqlite rowid alias |
| `title` | `TEXT NOT NULL` | trimmed server-side before insert (`server.py:43`); empty-after-trim rejected with `422 {"error": "title_required"}` (`server.py:44-45`) |
| `slug` | `TEXT NOT NULL` | derived from `title` via `slugify()` (`app/util.py`); **not unique** — no DB constraint, and collisions are possible/known (`util.py:5` comment) |
| `priority` | `TEXT CHECK (priority IN ('low','med','high'))` | accepts `"1"/"2"/"3"` (mapped to low/med/high) OR the words directly, or any other string that isn't `1`/`2`/`3` is passed through as-is and only succeeds if it happens to already be `low`/`med`/`high` — otherwise the sqlite `CHECK` constraint raises at insert (`server.py:47-49`; uncaught — see Invariants) |
| `status` | `TEXT NOT NULL CHECK (status IN ('open','closed'))` | set to `'open'` at creation (`server.py:51`), only transition is `open -> closed` via the close endpoint (`server.py:70`) |
| `assignee_id` | `INTEGER REFERENCES users(id)` | **defined in schema, never set or read by any route.** No code path assigns a ticket. Static finding, not in problem brief — flagged in `docs/00-overview.md`. |
| `created_at` | `DATETIME NOT NULL` | `datetime.now().isoformat()` — naive local time, no timezone (`server.py:52`, self-flagged in-source: "naive local time!"); see OQ-005 |
| `closed_at` | `DATETIME` (nullable) | same naive-local-time pattern, set on close (`server.py:71`) |

## Lifecycle

```
(create) -> open --close--> closed
```

Single one-way transition, enforced by the `WHERE status != 'closed'` guard on the close query
(`server.py:70`) — closing an already-closed ticket is a no-op (`rowcount == 0`), returns
`{"closed": false}` (`server.py:73,77`), and — because `changed` is falsy — **does not** re-send
the close notification email. No `open`-only reopen path exists anywhere.

## Invariants

- **Enforced (DB constraint, evidence: `db/schema.sql:5-6`)**: `priority` must be one of
  `low`/`med`/`high` at the storage layer. The application-layer mapping (`server.py:48-49`)
  only covers `"1"`/`"2"`/`"3"`; any other unmapped string is passed straight to the INSERT and
  will raise an unhandled `sqlite3.IntegrityError` (500) if it doesn't happen to already be a
  valid value. **This is a real, evidenced defect the problem brief does not mention** — not
  ported as a REPAIR (no PB backs it) but flagged; see `docs/open-questions.md` if a ruling to
  fix it is wanted. Default disposition: preserve the crash-on-bad-input behavior as FIXED,
  since no PB sanctions changing it, but this is exactly the kind of unsanctioned-looking bug
  Design Principle 9 says must not be silently fixed.
- **Enforced (DB constraint)**: `status` must be `open`/`closed` (`db/schema.sql:6`).
- **NOT enforced**: `slug` uniqueness — no unique index, confirmed collision-possible by the
  code's own comment (`util.py:5-6`). FIXED (preserve) per Design Principle 9 — no PB names this.
- **NOT enforced anywhere**: `assignee_id` referential population — the FK constraint exists at
  the DB layer (`REFERENCES users(id)`) but nothing in the app ever sets a non-null value, so it
  is vacuously true today. Out of behavioral scope for the first-pass rewrite (see overview).

## Read-path quirk (FIXED, evidence-limited)

`GET /api/tickets/<id>` returns HTTP `200` with `{}` when the id doesn't exist, not `404`
(`server.py:61-63`, explicit comment: "historical quirk ... the legacy UI depends on it"). No
legacy UI was included in this handover, so the claim "the UI depends on it" is sourced from the
comment only, not verified against an actual consumer. See OQ-001.
