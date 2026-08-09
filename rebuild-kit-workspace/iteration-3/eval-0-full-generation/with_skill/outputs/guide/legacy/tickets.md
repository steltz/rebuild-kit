# **Tickets** (how it works today)

Four routes, all in `ticketd/app/server.py`, no separate module: list, create, get-by-id, close.
Full behavioral detail: `docs/features/draft/tickets-crud.md`, `docs/domain/tickets.md`.

**List** (`GET /api/tickets`) is the workhorse — 61.75% of all sampled traffic. No pagination, by
design-not-accident: a code comment says the UI relies on getting everything and filtering
client-side. Optional `?status=` filters exact-match at the DB level, with one wrinkle a P9 audit
caught: an *empty* `?status=` value doesn't filter at all (falsy check treats it like the param
was never sent) — different from a junk value like `?status=bogus`, which correctly returns an
empty array.

**Create** (`POST /api/tickets`) requires a non-empty (after trim) title, accepts `priority` as
either `"1"/"2"/"3"` or the words `low`/`med`/`high` (a comment says both client shapes must keep
working), and — this is the part support has complained about — never checks whether the derived
slug already belongs to another ticket. "Fix DB" and "fix db!" both become `fix-db`, both succeed,
nothing disambiguates them (PB-003). What the fix should be is genuinely undecided — see OQ-001.
A P9 audit also found that `slugify()` can produce an *empty* slug (an all-punctuation title) or
one ending in a stray hyphen (an unlucky 64-character truncation boundary) — nobody had noticed
either before.

**Get** (`GET /api/tickets/<id>`) has the single most load-bearing quirk in this whole app: a
missing ticket returns `200 {}`, not `404`. A code comment says the legacy UI depends on exactly
this, and since UI changes are out of scope for this rewrite (PB-006), it stays.

**Close** (`POST /api/tickets/<id>/close`) is idempotent by construction (a `WHERE status !=
'closed'` guard) and is the other half of PB-001: on a real open→closed transition, it sends an
email — synchronously, in-request — to a single hardcoded address, `watchers@example.internal`.
That's the 40-minute outage in one line of code.
