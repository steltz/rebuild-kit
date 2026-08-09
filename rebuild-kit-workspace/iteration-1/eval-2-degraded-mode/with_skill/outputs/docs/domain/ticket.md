# Entity: Ticket

Table `tickets` (`ticketd/db/schema.sql:1-10`).

## Fields
| field | type | source | notes |
|---|---|---|---|
| id | INTEGER PK | schema.sql:2 | rowid; exposed in API responses |
| title | TEXT NOT NULL | schema.sql:3 | app rejects empty/whitespace with 422 `title_required` (`app/server.py:43-45`) |
| slug | TEXT NOT NULL | schema.sql:4 | derived: `slugify(title)` at create (`app/server.py:52`); **not unique** — collisions acknowledged in `app/util.py:5`. Never regenerated after create; no read path uses it (OQ-003) |
| priority | TEXT CHECK low/med/high | schema.sql:5 | app coerces "1"/"2"/"3"→low/med/high, default "med" (`app/server.py:47-49`); any OTHER string is passed through to the INSERT and the CHECK rejects it → unhandled IntegrityError → 500 (see WO-003 edge cases) |
| status | TEXT NOT NULL CHECK open/closed | schema.sql:6 | lifecycle below |
| assignee_id | INTEGER REFERENCES users(id) | schema.sql:7 | **no code path writes or reads it** (grep: only schema mentions it); FK declared but unenforced at runtime (no `PRAGMA foreign_keys`, `app/server.py:20-24`) → OQ-002 |
| created_at | DATETIME NOT NULL | schema.sql:8 | naive local-time ISO string (`app/server.py:52`) |
| closed_at | DATETIME | schema.sql:9 | set on close (`app/server.py:71`); naive local time |

## Lifecycle
```
open --POST /api/tickets/<id>/close--> closed        (terminal; no reopen path exists)
```
- Created as `'open'` (hardcoded in INSERT, `app/server.py:51`).
- Close is idempotent-ish: `WHERE ... AND status != 'closed'` (`app/server.py:70`) — closing a
  closed ticket returns `{"closed": false}` and sends **no** email; closing a missing id behaves
  identically (`{"closed": false}`, no 404).
- No update, delete, or reopen route exists.

## Invariants (enforcement-cited)
- title non-empty: app-enforced on the only write path (`app/server.py:43-45`) + NOT NULL (DDL).
- priority vocabulary low/med/high: **DB-enforced** (CHECK, schema.sql:5). App-side coercion is
  partial — non-numeric junk reaches the DB and 500s.
- status vocabulary open/closed: DB-enforced (CHECK, schema.sql:6); app only ever writes those two.
- slug uniqueness: **NOT an invariant** — nothing enforces it; do not add uniqueness without a
  ruling (OQ-003).
- close notification: exactly one email to hardcoded `watchers@example.internal` per successful
  transition (`app/server.py:73-76`); none on no-op close.
