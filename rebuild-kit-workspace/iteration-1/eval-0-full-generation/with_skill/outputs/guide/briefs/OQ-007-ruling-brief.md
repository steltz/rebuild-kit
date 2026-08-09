# Ruling needed: OQ-007 — Invalid priority values: preserve the 500 or validate?

**What's being decided.** Sending `priority: "urgent"` (or `2.0`, or `null`) today crashes
into the DB CHECK constraint and returns a 500 HTML page — captured live in trace
`ask-priority-500` (`ticketd/app/server.py:47-49` + `ticketd/db/schema.sql:5`, audit
AD-003 for the float/null edge).

**Why it's flagged.** PB-005 says no UI changes — and the UI never sends invalid
priorities (zero 4xx-on-create in the 30-day log beyond title_required patterns; the 500s
observed are OQ-008's separate mystery). A 422 would be invisible to the UI and strictly
saner; but an unsanctioned 500→422 change is exactly the drift this workspace exists to
prevent, so it needs your signature, not our judgment.

**Where it bites.** WO-002 (M1). Until ruled: modern preserves a 500-class response for
such input; the trace stays out of acceptance (`t2-edge-ask` set).

**Options & consequences.**
1. Sanction 422 `{"error": "invalid_priority"}` → small PB amendment + divergence entry;
   cleanest.
2. Preserve 500-class → bug-for-bug fidelity; costs nothing but dignity.

**Recommendation (non-binding).** Option 1 — nothing observable depends on the 500.

---
Ruling: ____________  Ruled by: ________  Date: ______
