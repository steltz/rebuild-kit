# Design: slug collisions

**Status: PROPOSED DEFAULT, NOT DECIDED.** Unlike the SMTP and MD5 fixes,
nobody has picked an approach for this one. This document proposes a
default so the plan is executable without a live person to ask, but it is
the single item in this workspace most likely to be wrong for reasons only
the product/support side would know (e.g. "support pastes slugs into
customer emails and they need to stay short," or "there's already a
convention we use elsewhere in the company"). **Flagged again in
`03-OPEN-QUESTIONS.md` item 2 — read that before executing Phase 2
(`plans/02-core-tickets-api.md`, Task 1), which implements the algorithm
below as part of ticket creation (the slug fix isn't separable from the
create endpoint, since the unique index is created in Phase 1 and any
`POST /api/tickets` after that must already handle collisions or it will
fail outright — see Phase 1's Task 3 preflight check for the historical-data
side of this too).**

## The problem, precisely

```python
def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64]
```

Lossy by design (that's fine — slugs are supposed to be lossy/normalized).
The actual bug is that nothing enforces uniqueness: `"Fix DB"` and
`"fix db!"` both produce `"fix-db"`, both get inserted, and now two tickets
share a slug with no error, no warning, nothing. If anything downstream
(links, search, the UI) keys off slug instead of id, this is silently wrong
today.

## Options considered

1. **Numeric suffix on collision** (`fix-db`, `fix-db-2`, `fix-db-3`, ...).
   Human-readable, deterministic, easy to reason about in support tickets
   ("oh, this is the second one"). Requires a retry loop or a `SELECT COUNT`
   before insert (race-prone under concurrency unless done carefully — see
   below).
2. **Append the ticket's own id once known** (`fix-db-482`). Fully
   deterministic, zero collision risk by construction (ids are unique by
   definition), no retry loop needed at all — insert first, then derive slug
   from `(base_slug, id)` in the same transaction. Less human-friendly
   (`fix-db-482` reads as "ticket 482," not "the second fix-db"), and changes
   the base case too: *every* slug gets an id suffix, not just colliding
   ones, which is a bigger visible change than strictly necessary to fix the
   bug.
3. **Short random suffix on collision** (`fix-db-a1b2`). Avoids the "how many
   fix-db's are there" implication of sequential numbering, but is harder to
   eyeball/compare in support conversations and non-deterministic (annoying
   for tests).

**Recommendation: option 1 (numeric suffix, collision-only), implemented via
insert-with-unique-constraint-and-retry rather than check-then-insert:**

```python
def create_ticket_slug(conn, title: str) -> str:
    base = slugify(title)
    candidate = base
    suffix = 1
    while True:
        try:
            # the actual ticket INSERT includes `slug=candidate`;
            # tickets_slug_key is a UNIQUE INDEX (see DESIGN-architecture.md)
            return insert_ticket_with_slug(conn, candidate)  # raises on unique violation
        except UniqueViolation:
            suffix += 1
            candidate = f"{base}-{suffix}"[:64]   # keep the 64-char cap from legacy slugify
            # loop and retry the insert with the new candidate
```

Why retry-on-conflict instead of "count existing rows with this prefix,
then pick the next number": the count-then-insert approach has a race
condition (two concurrent creates with the same title can both count 0 and
both try to insert the bare slug) — the DB unique index is the only thing
that can actually guarantee no collision under concurrency, so the code has
to be written to expect and handle the conflict anyway. Given that, doing
the numbering via retry-on-conflict is both simpler and actually correct,
instead of doing a count *and* still needing conflict-handling as a
fallback.

Base case (no collision) costs nothing extra: one insert, succeeds
immediately, `candidate == base`. Collisions (rare, per the bug reports)
cost one extra round trip per collision.

## What changes for callers

`POST /api/tickets`'s response (`{"id", "slug"}`) now returns the
*persisted* slug, which may have a numeric suffix the caller didn't
literally ask for. This is the intended fix, not a side effect to hide.
Existing tickets are unaffected (no backfill/renumbering of already-stored
slugs — see migration plan; retroactively renaming existing slugs would
break any existing external links to them, which is a worse problem than
the one being fixed).

## Open items this default does not resolve

- Should existing colliding slugs already in the SQLite data be
  disambiguated during migration, or left as-is (accepting that a handful of
  old tickets keep sharing a slug forever)? Default: **leave as-is** — see
  `plans/06-migration-and-cutover.md`. Changing historical slugs risks
  breaking bookmarked/shared links more than it's worth for a handful of old
  rows.
- Is a numeric suffix acceptable, or does the org have a house style for
  this already (some companies always suffix with id, some use random
  short codes, etc.)? This is exactly the kind of call that should go back
  to whoever owns product/support here — see `03-OPEN-QUESTIONS.md`.
