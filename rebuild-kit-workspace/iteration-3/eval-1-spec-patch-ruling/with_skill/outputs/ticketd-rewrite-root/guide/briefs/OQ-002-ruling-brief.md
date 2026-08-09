# Ruling needed: OQ-002 — Are slug collisions acceptable, and if not, what is the target behavior?

**What's being decided.** Ticket slugs are generated from the title (lowercased, non-alphanumeric
runs collapsed to `-`, truncated to 64 chars). Two different titles that normalize to the same
text — e.g. "Fix DB" and "fix db!" — currently produce the same slug, and the legacy app makes no
attempt to disambiguate them.

**Why it's ambiguous.**
- Reading A: collisions are a known-tolerated quirk — evidence: `ticketd/app/util.py:4-6` (the
  code comment names the collision but does nothing about it)
- Reading B: PB-003 reports them as a defect — evidence: `docs/problem-brief.md` PB-003
  ("Fix DB" and "fix db!" produce the same slug; reported by support)

**Where it bites.** Affected flow: ticket creation (`POST /api/tickets`). Blocks: WO-002.
Usage: no runtime evidence available for this workspace (P2 inactive) — severity is support-reported, not traffic-weighted.

**Options & consequences.**
1. Leave as-is (Reading A) → cheapest, but ports a known support-reported defect forward unfixed.
2. Enforce uniqueness, numeric suffix on collision (`-2`, `-3`, ...) → matches user expectation
   that a slug identifies one ticket; requires a write-time uniqueness check rather than a bare
   insert.
3. Defer → WO-002 stays blocked; ticket CRUD (a milestone-1 work order) cannot proceed.

**Recommendation (non-binding).** PB-003 is a specific, reproduced support complaint, not a
hypothetical — favors option 2.

---
Ruling: Not acceptable (Reading B) — slugs must be unique; on collision append a numeric suffix
(-2, -3, ...); existing stored slugs are not migrated.
Ruled by: Dana Ruiz   Date: 2026-08-09

(Recorded in docs/open-questions.md; propagated via spec-patch. This page reflects the ruling as
resolved — see docs/features/WO-002-ticket-crud.md and
verification/replay/expected-divergences.yaml#ED-002 for the propagated spec/verification delta.)
