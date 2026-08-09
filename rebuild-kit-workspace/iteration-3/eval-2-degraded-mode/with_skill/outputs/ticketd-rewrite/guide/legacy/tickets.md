# Tickets (how it works today)

Four routes, all in `legacy/app/server.py`, all reading/writing one `tickets` table with no
pagination and no auth. A ticket's `title` is required and gets slugified for a shareable-looking
URL fragment (`app/util.py:slugify`) — but the slug is decorative, not a key: nothing prevents
two different titles from producing the same slug (`legacy/app/util.py:5-6` documents this with
its own example, "Fix DB" and "fix db!" both becoming `fix-db`). `priority` is one of three
values, but the create endpoint accepts either the word or a legacy numeric code (`"1"/"2"/"3"`)
because, per an in-code comment, "clients send both, both must keep working."

**The one quirk worth knowing before you read the code and think it's a bug:** fetching a
ticket that doesn't exist returns `200 {}`, not a 404. This is deliberate — the comment at the
call site says the legacy UI depends on it (`legacy/app/server.py:62-63`). Closing a ticket is
idempotent (closing an already-closed ticket is a harmless no-op) and has no 404 case either — a
close on a nonexistent id just reports `{"closed": false}`.

**What actually breaks:** closing a ticket sends a notification email to a single hardcoded
address, `watchers@example.internal`, synchronously, inside the request — see
`guide/legacy/notification.md` and `PB-001`. And two crash paths exist that nothing in the
problem brief flagged: an out-of-range `priority` or a non-string `title` both bypass validation
and hit the database's own constraint, surfacing as a raw Flask 500 instead of a JSON error
(found during the P9 audit — see `docs/open-questions.md#OQ-005`, `#OQ-006`).

See `docs/features/WO-001-tickets-core.md` and `docs/features/WO-002-tickets-close.md` for the
full, cited behavior list.
