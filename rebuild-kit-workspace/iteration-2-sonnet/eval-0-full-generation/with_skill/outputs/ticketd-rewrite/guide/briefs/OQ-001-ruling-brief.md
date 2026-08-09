# Ruling needed: OQ-001 — What should happen when a new ticket's slug collides with an existing one?

**What's being decided.** Every ticket gets a URL-friendly `slug` derived from its title. Today
two differently-titled tickets can produce the identical slug ("Fix DB" and "fix db!" both
become `fix-db`) and the app doesn't notice or care — no error, no adjustment, both rows exist
with the same slug. Support keeps running into this. Leadership named it as a problem to fix
without naming the fix (`docs/problem-brief.md` PB-003) — this ruling is that missing decision.

**Why it's ambiguous.** The *outcome* isn't in question — slugs should be unique, that much is
already ratified. What's genuinely open is the *mechanism* for a collision:
- Reading A — **Reject the create.** Return `422` and ask the client to pick a different title
  (or the backend to disambiguate some other way). Matches how `title` emptiness is already
  validated. Changes the API contract for a case that's silently allowed today — new behavior
  the current UI has never had to handle.
- Reading B — **Auto-suffix.** `fix-db`, then `fix-db-2`, `fix-db-3`, etc. The ticket still
  gets created (same as today); only the derived slug field changes. Lowest client-visible risk.
- Reading C — **Always include the ticket's own id in the slug** (`fix-db-1042`). Guarantees
  uniqueness by construction, but changes the slug format for *every* ticket, not just the ones
  that would've collided — a bigger visible change than A or B for tickets that were never
  going to collide in the first place.

**Where it bites.** Affected flow: ticket creation (`POST /api/tickets`), the single
highest-write-volume route in the app (~21% of measured traffic — see `usage-weights.json`,
noting that number's log-window caveat). Blocks: `docs/features/WO-005-slug-uniqueness.md`
directly; `docs/features/WO-010-data-migration.md` indirectly (the migration needs to know the
backfill policy for any pre-existing collisions, which is a related but separate call —
see `docs/migration/mapping.md`).

**Options & consequences.**
1. **Reject (422).** Users occasionally get an error creating a ticket with a very generic
   title and have to retitle it. Simple to implement and reason about; changes visible
   behavior for a currently-silent case.
2. **Auto-suffix.** No user-visible friction at create time; slugs become slightly less
   predictable/pretty for the (presumably rare) colliding case. Simplest to implement without
   touching the create flow's success path at all.
3. **Id-in-every-slug.** Solves it permanently and simply, but is the most visible change of
   the three — every ticket's slug looks different from today's format, not just the
   colliding ones. Worth asking whether anything external (bookmarks, links, another system)
   depends on today's slug format before choosing this.
4. **Defer.** WO-005 stays blocked; PB-003 stays unfixed past this rewrite's initial rollout.
   Given this was leadership's explicitly named third problem, deferring indefinitely
   contradicts the brief's own framing — but deferring past Milestone 0/1 specifically (to let
   more pressing work land first) is reasonable and doesn't require this brief to be resolved
   today.

**Recommendation (non-binding).** No evidence in this codebase favors one reading over another
— this is a genuine product/UX call, not something the legacy code hints at. Option 2
(auto-suffix) has the smallest blast radius if a fast decision is needed and no one has a
strong opinion; option 3 is worth strong consideration if any external system is known to
reference ticket slugs directly (unconfirmed either way — see `docs/domain/glossary.md`'s note
on this).

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
