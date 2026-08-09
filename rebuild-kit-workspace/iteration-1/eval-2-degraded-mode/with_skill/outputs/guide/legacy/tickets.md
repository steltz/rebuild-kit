# tickets (how it works today)

The whole subsystem is four route functions in `ticketd/app/server.py:27-77` plus a 3-line
slugifier (`ticketd/app/util.py`). SQLite, one table, no service layer.

## The flows
- **Create** (`POST /api/tickets`): strip the title (the stripped value is what persists —
  audit A-05), reject empty with 422 `title_required`, coerce priority aliases 1/2/3 →
  low/med/high (both numbers and strings — "clients send both, both must keep working",
  server.py:47), derive the slug, insert with status `open` and a **naive local-time**
  timestamp (the code's own comment: "naive local time!", server.py:52). Respond 201 with
  just `{id, slug}`.
- **List** (`GET /api/tickets`): everything, newest first, no pagination — the UI "relies on
  getting everything and filtering client-side" (server.py:35). `?status=x` filters exactly;
  `?status=` (empty) turns the filter off entirely (truthiness, server.py:32 — audit A-03).
- **Get** (`GET /api/tickets/<id>`): the famous quirk — a missing id returns **200 with
  `{}`**, never 404, and the comment says the legacy UI depends on it (server.py:61-63).
- **Close** (`POST /api/tickets/<id>/close`): one guarded UPDATE (`status != 'closed'`), so
  re-closing and closing a ghost id both return `{"closed": false}` quietly. A successful
  close emails `watchers@example.internal` — synchronously, in the request thread, which is
  PB-001: "SMTP outages take ticket-closing down with them" (server.py:75).

## The archaeology (why it's weird)
- The 500s on bad input aren't handling, they're absence of handling: unknown priorities fly
  past the alias map into the DB CHECK and explode (IntegrityError → 500); numeric titles
  explode earlier on `.strip()`. The rewrite is sanctioned to turn these into 422s
  (ED-004a/b) — the only input-handling change allowed.
- Slugs collide by design-neglect ("Fix DB" and "fix db!" share a slug — util.py:5 admits
  it) and nothing ever reads them (OQ-003). We port the derivation bit-for-bit anyway.
- The close path commits BEFORE it emails, so an SMTP failure gives the caller a 500 for a
  close that actually happened. This failure shape dies with ED-001.
- Under error, the per-request DB connection leaks with an open transaction, write-locking
  the DB for ~5s — we observed this while capturing goldens (harness README, probe
  isolation).

Evidence base: docs/features/draft/tickets.md (audited), traces tickets-* in
verification/replay/traces/core.legacy.jsonl.
