# Entity: Ticket

## Fields
(source: `legacy/db/schema.sql:1-10`, cross-checked against write paths in
`legacy/app/server.py`)

| Field | Type | Constraint | Notes |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | SQLite rowid alias |
| `title` | TEXT | NOT NULL | Trimmed on write (legacy/app/server.py:43: `.strip()`); empty-after-trim rejected with 422 `title_required` (legacy/app/server.py:44-45) |
| `slug` | TEXT | NOT NULL | Derived from `title` via `slugify()` (legacy/app/util.py:4-6); **not unique at the DB level** — no UNIQUE constraint in schema, and `slugify` is documented as collision-prone ("Fix DB" and "fix db!" collide, legacy/app/util.py:5). Recomputed (not stored-then-reused) on every read that needs it, e.g. in the create response (legacy/app/server.py:55). |
| `priority` | TEXT | CHECK IN ('low','med','high') | Accepted from clients as either the string values directly or the strings `"1"`/`"2"`/`"3"` mapped to `low`/`med`/`high` (legacy/app/server.py:47-49, comment: "clients send both, both must keep working"). Defaults to `"med"` if absent. |
| `status` | TEXT | NOT NULL, CHECK IN ('open','closed') | Set to `'open'` on create (legacy/app/server.py:51); only legal transition observed in code is open→closed via the close route (legacy/app/server.py:69-71); no reopen path exists anywhere in the tree. |
| `assignee_id` | INTEGER | REFERENCES users(id) | **Never read or written by any route** in the legacy tree — see `docs/open-questions.md#OQ-004`. |
| `created_at` | DATETIME | NOT NULL | `datetime.now().isoformat()` — naive local time, no timezone (legacy/app/server.py:52, flagged in-code with a `# naive local time!` comment). This is a latent correctness issue if the app ever runs across multiple timezones/hosts, but it is **not** in the problem brief, so it is not a REPAIR target — carried forward as FIXED unless ruled otherwise. |
| `closed_at` | DATETIME | nullable | Set only by the close route, same naive-local-time pattern (legacy/app/server.py:71). |

## Lifecycle

```
(none) --create--> open --close--> closed
```
- Create: `POST /api/tickets` (legacy/app/server.py:40-55).
- Close: `POST /api/tickets/<id>/close` (legacy/app/server.py:67-77) — idempotent guard via
  `AND status != 'closed'` in the UPDATE's WHERE clause (legacy/app/server.py:70); the response
  body's `closed` field reflects whether this specific call caused the transition
  (`rowcount`-based), not whether the ticket is currently closed.
- No delete, no reopen, no edit-after-create route exists in the legacy tree.

## Invariants

- `status` domain constrained at the DB level (`CHECK` in schema) — enforced, not just suggested.
- `priority` domain constrained at the DB level (`CHECK` in schema) **and** normalized at the
  application layer before insert (legacy/app/server.py:47-49) — both layers agree, no conflict.
- Title non-empty: enforced only at the application layer (legacy/app/server.py:44-45), **not**
  at the DB level (schema only has `NOT NULL`, which whitespace-only or a stripped-empty string
  would not violate if inserted directly). Single write path in this codebase, so no ASK — but
  note for the rewrite that the DB alone does not guarantee this.
- Slug uniqueness: **not enforced anywhere**, application or DB. Documented collision behavior,
  carried forward as FIXED (this is existing, evidenced behavior, not brief-flagged) unless a
  human ruling promotes it to a PB entry via `docs/open-questions.md`.
- `GET /api/tickets/<id>` for a nonexistent id returns `200 {}`, not 404 — explicitly commented
  as a deliberate legacy-UI dependency (legacy/app/server.py:62-63). FIXED; do not "fix" this
  without a ruling (see `modern/CLAUDE.md` architecture rules).
- `assignee_id REFERENCES users(id)` is declared in the DDL but **not enforced**: SQLite disables
  foreign-key checking by default and `db()` (legacy/app/server.py:20-24) never issues
  `PRAGMA foreign_keys=ON`. Moot in practice since nothing ever sets `assignee_id` (see OQ-004),
  but worth carrying into `docs/migration/mapping.md` — the target Postgres schema enforces FKs
  by default, which is a behavior CHANGE (mechanism, not observable API behavior — FREE) that a
  real assignee_id/users dataset could surface as new constraint violations at migration time if
  OQ-004 reading B turns out to be correct. (Found by the P9 independent audit.)
