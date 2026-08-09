# Ruling needed: OQ-006 — Should a non-string `title` crash with a raw 500?

**What's being decided.** Sending a ticket-create request with a non-string `title` (a JSON
number, array, or object) currently crashes with an unhandled `AttributeError` on `.strip()`,
surfacing as a raw 500 — found by the P9 adversarial audit. Same question as OQ-005, different
field: REPAIR (validate the type) or FIXED (carry the crash forward)?

**Why it's ambiguous.** Identical shape to OQ-005:
- Reading A: Unsanctioned — every other validation failure returns a proper JSON error; this one
  doesn't, and nothing suggests that was deliberate.
- Reading B: Not brief-flagged; could be an accepted tradeoff for an internal tool.

**Where it bites.** `WO-001`, same location as the OQ-005 finding. `blocks: []` — WO-001 already
carries the crash forward as FIXED by default pending this ruling.

**Options & consequences.** Same as OQ-005:
1. REPAIR (type-check before `.strip()`, return `422`) → consistent with every other validation
   path in the app.
2. FIXED (carry forward exactly) → zero fidelity risk, ships the raw-500 experience.
3. Defer → proceeds under FIXED by default.

**Recommendation (non-binding).** Same as OQ-005 — consider ruling OQ-005 and OQ-006 together,
since they're the same class of gap found by the same audit pass and the same fix pattern
(reject non-conforming input before it reaches the database) covers both.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
