# tickets (how it works today)

The heart of the system: one table (`tickets`), four routes, two states. A ticket is born
`open` via `POST /api/tickets`, lives unmodified (there is no edit, no reopen, no delete),
and dies `closed` via `POST /api/tickets/<id>/close`. That's the entire lifecycle
(`docs/domain/ticket.md`).

**Listing** carries 62% of all traffic (`usage-weights.json`): `GET /api/tickets` returns
*every* ticket, newest first, with an optional `?status=` filter — no pagination, by
design: the UI fetches everything and filters client-side (`ticketd/app/server.py:35`,
draft spec TL-2). Any rewrite instinct to paginate is a UI change, and UI changes are out
of scope (PB-005).

**Creation** strips the title, derives a slug, coerces priority ("1"/"2"/"3" from older
clients map to low/med/high — both styles are still in the wild, TC-4), and returns
201 `{id, slug}`. Two sharp edges:
- *Slugs collide.* "Fix DB" and "fix db!" produce the same slug and nothing stops them
  (PB-003 — support's recurring complaint; frozen in traces `tickets-create-006/007`).
  The fix is undecided: **OQ-001, ruling needed.**
- *Unknown priorities 500.* Anything outside the known values sails past validation into
  the DB CHECK and explodes (TC-5/TC-12, OQ-007).

**The archaeology.** `GET /api/tickets/<id>` for a missing ticket returns **200 with `{}`**,
not 404 — a historical quirk the legacy UI depends on (`ticketd/app/server.py:62-63`). It
looks like a bug; it is a load-bearing contract (TG-3), and the rewrite keeps it.

**Closing** is idempotent (WHERE-guarded UPDATE) and answers `{"closed": bool}` — false
both for "already closed" and "never existed", indistinguishable (CL-2). On a real
transition it emails `watchers@example.internal` — synchronously, inside the request,
which is why the June SMTP outage stopped anyone from closing tickets (PB-001, and the
whole reason this rewrite exists). See `guide/flows/close-ticket.md` for the storyboard.
