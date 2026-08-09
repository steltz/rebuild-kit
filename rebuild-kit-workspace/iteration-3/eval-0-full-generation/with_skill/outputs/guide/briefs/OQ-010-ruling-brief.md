# Ruling needed: OQ-010 — Should any legacy `reset_tokens` rows be migrated, or start clean?

**What's being decided.** Whether existing rows in the legacy `reset_tokens` table should be
carried into the new Postgres database at all, given the whole table is being replaced by a
different security mechanism (PB-002/WO-003).

**Why it's ambiguous.** The generator has a clear recommendation (don't migrate) but flags this
as a decision it shouldn't finalize alone, since "don't migrate this data" is itself a
data-destructive-adjacent choice.

**Where it bites.** Blocks: WO-005 (data migration) can't fully close without this ruling.
Affects only the `reset_tokens` table — `tickets` and `users` migration proceeds independently.

**Options & consequences.**
1. **Don't migrate (recommended default).** Every existing row is either already consumed,
   already past its 30-minute window, or represents exactly the weak-credential pattern being
   replaced — none have forward value under the new mechanism. Simplest, cleanest cutover.
2. **Migrate for audit-trail purposes**, stripped of the token value itself (just "who requested a
   reset and when"). Only worth doing if there's a compliance or audit reason this brief doesn't
   have visibility into.

**Recommendation (non-binding).** Option 1, unless someone in a compliance/audit role specifically
needs historical reset-request records preserved — in which case that's worth surfacing before
cutover, not after.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
