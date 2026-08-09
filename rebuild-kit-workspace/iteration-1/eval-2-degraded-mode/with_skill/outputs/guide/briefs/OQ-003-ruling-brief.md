# Ruling needed: OQ-003 — Slugs: does anything read them?

**What's being decided.** Whether slug collisions/emptiness matter to any consumer.

**Why it's ambiguous.**
- Reading A: decorative — no route reads or queries by slug; not UNIQUE
  (ticketd/db/schema.sql:4); collisions acknowledged in code (ticketd/app/util.py:5).
- Reading B: the UI uses slugs from list/create responses for display/URLs — they appear in
  both responses (ticketd/app/server.py:37,55).

**Where it bites.** Nothing is blocked — WO-003 ports the derivation exactly, satisfying
both readings. A ruling only permits future cleanup.

**Options & consequences.** 1. Confirm decorative → optional later simplification. 2. Name
the consumer → derivation stays load-bearing forever. 3. Defer → zero cost.

**Recommendation (non-binding).** Defer; ask only if the UI team is in the room anyway.

---
Ruling: ____________  Ruled by: ________  Date: ______
