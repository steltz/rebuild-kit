# Ruling needed: OQ-001 — What should happen on a ticket-title slug collision?

**What's being decided.** Two tickets whose titles normalize to the same slug (e.g. "Fix DB" and
"fix db!" both become `fix-db`) currently both succeed, both get the same slug, and nothing tells
them apart downstream. Support has hit this in practice. Nobody has decided what the fix should
be — that's direct testimony from the person who commissioned this rewrite, not an inference.

**Why it's ambiguous.** There's no disagreement about the current behavior (it's fully evidenced
and traced) — the ambiguity is entirely about what, if anything, should replace it. No prior
decision or precedent exists to read from.

**Where it bites.** Affected flow: ticket creation (`guide/legacy/tickets.md`,
`docs/features/WO-002-tickets-create-get-close.md`). Blocks: nothing currently — WO-002 ships the
legacy-faithful (collision-permitting) baseline without waiting on this ruling, since preserving
observed behavior needs no sanction. A ruling only matters for a *future*, separately-scoped
enhancement. Usage: create is the second-highest-traffic route (21.15% of sampled requests).

**Options & consequences.**
1. **Reject the second create with `409 Conflict`.** Users retitle and retry. New behavior, not
   currently evidenced — a real UX change (create can now fail for a reason it never used to).
2. **Auto-disambiguate** by appending a suffix (`-2`, `-3`, …) or the numeric id. Every create
   still succeeds, but "slug" stops being purely derived from title — it becomes stateful.
3. **Stop treating slug as meaningful at all** — display-only, non-unique, key everything off
   `id` the way `GET /api/tickets/<id>` already does. Lowest implementation risk, sidesteps the
   question entirely by declaring it doesn't matter.
4. **Defer.** WO-002 ships as-is; support keeps living with collisions until this is revisited.

**Recommendation (non-binding).** Option 3 is the lowest-risk path if slug was never meant to be
an identifier in the first place — nothing in the legacy code treats it as one (routes key off
`id`, not `slug`). If support *does* rely on slugs as if they were unique in some external
context (a bookmarked URL, a support-ticket reference in an email), that changes the calculus
toward option 1 or 2 — worth asking support directly before ruling, since the evidence available
to this workspace can't answer that question.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
