# Tickets (how it works today)

Four routes, all in `legacy/app/server.py`, all hitting a single SQLite `tickets` table.

**List** (`GET /api/tickets`) returns everything, unpaginated, newest first, with an optional
exact-match `status` filter — but only when the query param is non-empty; `?status=` (present,
blank) is treated the same as omitting it entirely (`server.py:32`, confirmed by the P9
adversarial audit after the original draft spec mis-described this as "when present" — see
`docs/features/draft/tickets-list-create-get.md`). The lack of pagination is deliberate per an
inline comment: the UI is expected to fetch everything and filter client-side.

**Create** (`POST /api/tickets`) requires a non-blank `title` (server-stripped, `422` on blank),
accepts `priority` as either a word (`low`/`med`/`high`) or a digit-string (`"1"`/`"2"`/`"3"`) —
a real, evidenced client dependency per an inline comment ("clients send both, both must keep
working") — and derives a `slug` from the title that is NOT guaranteed unique
(`docs/open-questions.md#OQ-005`). Two crash paths exist that nobody flagged until the P9 audit:
a non-string title or an explicit `null` priority reach an unhandled code path and surface as a
bare 500 (`docs/open-questions.md#OQ-009`).

**Get by id** (`GET /api/tickets/<id>`) has the single most interesting behavior in the whole
app: a missing ticket returns `200 {}`, not `404`. The legacy code comment doesn't hedge about
this — it says the UI depends on it. This is the clearest example anywhere in ticketd of a
"looks like a bug, is actually load-bearing" behavior, and it's the one thing this guide would
most want a new engineer to internalize before touching this route.

See `docs/domain/ticket.md` for the full field-by-field breakdown and invariants. A storyboarded
walk-through exists for the password-reset flow (`guide/flows/password-reset.md`) but not yet
for Tickets — the reset flow was prioritized because it's where both motivating defects (PB-001,
PB-002) live; a Tickets storyboard would be a good next addition using
`verification/replay/traces/tickets-legacy.jsonl`, which already has 18 real captured traces to
draw from.
