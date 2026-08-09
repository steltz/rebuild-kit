# Ruling needed: OQ-001 — What is the slug-collision fix? (PB-003)

**What's being decided.** Every ticket gets a URL-ish "slug" derived from its title.
Today, similarly-named tickets get the *same* slug — support keeps hitting this. The
rewrite is sanctioned to fix it (PB-003), but nobody has said what "fixed" means.

**Why it's ambiguous.** The problem is ratified, the target isn't.
- Today: `slugify` lowercases, collapses punctuation to `-`, truncates to 64 — "Fix DB"
  and "fix db!" → both `fix-db` — evidence: `ticketd/app/util.py:5` (its own comment
  admits it), no unique constraint (`ticketd/db/schema.sql:4`), frozen in traces
  `tickets-create-006/007`.
- Also in scope (audit AD-002): truncated slugs can end in `-`; an all-symbol/non-ASCII
  title slugs to the empty string.

**Where it bites.** WO-002 (create ticket, M1) — implemented legacy-exact until ruled;
its gate flags this. Migration (WO-007) inherits it: if slugs become unique, existing
collisions in prod data need a dedup policy. Usage: create is 21% of traffic. Notable:
**no code ever reads a slug back** — it is write-only in the API — so option 3 is genuinely
on the table.

**Options & consequences.**
1. Unique index + numeric suffix on collision (`fix-db`, `fix-db-2`) → intuitive; new
   divergence entry + migration dedup for historical rows; slugs become creation-order
   dependent.
2. Always-append short random suffix → collision-proof, stable algorithm, but every slug
   changes shape (UI display? PB-005 caution) and migration must regenerate or grandfather.
3. Declare collisions harmless (slug is display-only), keep legacy behavior, close PB-003
   as "working as intended" → zero work; support's complaint stays unexplained — worth
   asking support *where* the collisions actually hurt them.
4. Defer → WO-002 ships legacy-exact; a later ruling costs a spec-patch + re-run of the
   create replay set (cheap now, more re-verification after M1 closes).

**Recommendation (non-binding).** Ask support for the actual pain first (option 3 vs 1
hinges on it). If a fix is wanted, option 1 with migration dedup is the smallest surprise.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Record the ruling in docs/open-questions.md#OQ-001; spec-patch propagates it.)
