# **Tickets** (how it works today)

Four routes, all in `app/server.py`, all reading/writing one `tickets` table: list, create,
get-one, close. No separate service or model layer — Flask view functions talk to SQLite
directly (`server.py:27-77`).

**Listing** (`GET /api/tickets`) returns everything, unpaginated, newest first, with an
optional exact-match `status` filter — a deliberate choice ("the UI relies on getting
everything and filtering client-side," `server.py:35`), not an oversight. This is by far the
busiest route in the app: ~62% of all observed traffic (`usage-weights.json`, though that
number leans on a synthetic 1-hour log — see the orientation chapter's caveats).

**Creating** (`POST /api/tickets`) is where most of the interesting behavior lives: `title` is
required and trimmed; `priority` quietly accepts either words (`low`/`med`/`high`) or legacy
numeric codes (`"1"/"2"/"3"`) because, per a code comment, "clients send both, both must keep
working" (`server.py:46`); an out-of-range priority string isn't caught by the app at all — it
falls straight through to a SQLite `CHECK` constraint and comes back as an uncaught 500. The
new ticket's URL-friendly `slug` is computed once from the title and — this is the whole of
PB-003 — never checked for collisions against existing slugs. "Fix DB" and "fix db!" produce
the identical slug `fix-db`, and the database has no `UNIQUE` constraint to stop it. Support's
been hitting this for a while; nobody had decided the fix until this rewrite.

**Fetching one** (`GET /api/tickets/{id}`) has a quirk worth knowing before you "fix" it: asking
for a ticket that doesn't exist returns `200 {}` — an empty object, not a 404. A code comment
confirms this is intentional, and the frontend depends on it. It stays exactly as-is.

**Closing** (`POST /api/tickets/{id}/close`) is the route the June 2026 incident was about —
see `notifications.md`.

Read the full behavior-by-behavior breakdown, every claim cited to a source line, in
`docs/features/draft/tickets-{list,create,get,close}.md` — those were independently
adversarial-audited (`audit/report.md`) and are the actual spec; this page is the tour.
