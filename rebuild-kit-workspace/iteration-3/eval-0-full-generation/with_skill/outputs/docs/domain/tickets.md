# Entity: Ticket

Table: `tickets` (`ticketd/db/schema.sql:1-10`). Owned by the Tickets subsystem.

## Fields

| field | type (legacy) | nullable | notes |
|---|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | no | SQLite rowid alias, autoincrement-by-default behavior. |
| `title` | `TEXT NOT NULL` | no | Free text; only validated for non-empty-after-strip on create (`server.py:44-45`). No max length in DB or app. |
| `slug` | `TEXT NOT NULL` | no | Derived from `title` via `slugify()` (`util.py:4-6`): lowercase, `[^a-z0-9]+` → `-`, trimmed, truncated to 64 chars. **Not unique at the DB level and not checked for uniqueness at the app level** — see PB-003/OQ-001. Recomputed (not stored-then-reused) on every reference: `create_ticket()` calls `slugify(title)` twice (`server.py:51` and `:55`), independently — both calls are deterministic so this is idempotent, not a bug, but note it if refactoring the response construction. |
| `priority` | `TEXT CHECK IN ('low','med','high')` | yes (defaults `'med'` at the app layer, not DB) | App accepts `1`/`2`/`3` (int-as-string) or the words `low`/`med`/`high` from the client and maps 1→low, 2→med, 3→high (`server.py:47-49`); anything else is passed through as-is and can violate the DB CHECK constraint at insert time (uncaught — the app layer would raise a `sqlite3.IntegrityError`, which is not handled, i.e. results in a 500). No evidence of what the client actually sends beyond int-string/word forms; the CHECK-violation path is unexercised in the access-log sample (no 4xx on `POST /api/tickets` besides one unrelated auth 429). |
| `status` | `TEXT NOT NULL CHECK IN ('open','closed')` | no | Set to `'open'` at creation (`server.py:51`, hardcoded), flipped to `'closed'` only by `close_ticket()` (`server.py:70`). No other transition exists — no reopen. |
| `assignee_id` | `INTEGER REFERENCES users(id)` | yes | **Dead column** — no route reads or writes it. See `docs/domain/users.md`. |
| `created_at` | `DATETIME NOT NULL` | no | `datetime.now().isoformat()` — naive local time, no timezone (PB-010, OQ-006), set once at insert, never updated. |
| `closed_at` | `DATETIME` | yes | Same naive-local-time construction, set only by `close_ticket()` on the transition to closed (`server.py:71`). |

## Lifecycle / state machine

```
(create) -> open -> (close) -> closed
```

Single one-way transition. `close_ticket()`'s `UPDATE ... WHERE id = ? AND status != 'closed'`
guard (`server.py:69-71`) makes closing idempotent at the DB layer — a second close attempt on an
already-closed ticket is a no-op (`rowcount` 0, no email sent, response `{"closed": false}`, still
`200`). This guard is the *entire* enforcement of the one-way transition; nothing prevents a
direct DB write from reopening a ticket, but no app code path does so.

## Invariants

- **`status` ∈ {open, closed}** — enforced by DB CHECK (`schema.sql:6`). FIXED, trivially portable
  to a Postgres CHECK or enum type.
- **`priority` ∈ {low, med, high}** — enforced by DB CHECK (`schema.sql:5`), but the app-layer
  int→word coercion (`server.py:47-49`) is the *only* place that keeps client-sent values inside
  that set for the common cases; a client sending e.g. `"urgent"` is not rejected at the app layer
  and would fail at the DB layer with an unhandled exception. **Confirmed empirically in P7**
  (trace `tickets-create-invalid-priority-906`,
  `verification/replay/traces/tickets-crud.jsonl`, captured in isolation to avoid the
  connection-lock confound documented in PB-004): confidence upgraded from inferred-only to
  traced. Flagged for WO-002 to decide FIXED (preserve the 500-on-bad-priority behavior) vs. an
  uncontroversial hardening (422 with a clear error) — the brief doesn't authorize changing this
  silently, so default to FIXED and note the option.
- **`title` non-empty after `.strip()`** — enforced only in `create_ticket()` (`server.py:44-45`),
  a single write path (there's only one create path in this app, so "enforced on create, not on
  import" doesn't apply here — no import path exists, `legacy_import.py` is dead/do-not-port).
- **`slug` is NOT unique** — explicitly not an invariant; this is PB-003/OQ-001's subject.
- **`assignee_id` FK to `users.id`** — DB-level FK declared (`schema.sql:7`) but SQLite does not
  enforce FKs by default (no `PRAGMA foreign_keys=ON` visible anywhere in `server.py`), and no
  route ever sets `assignee_id`, so this constraint has never been exercised. Not evidenced as a
  real invariant — flagged in `docs/migration/census.md` for the Postgres DDL (P5/P6) to decide
  whether to keep, drop, or enforce it for the first time (FREE, since no observed behavior
  depends on it either way).
