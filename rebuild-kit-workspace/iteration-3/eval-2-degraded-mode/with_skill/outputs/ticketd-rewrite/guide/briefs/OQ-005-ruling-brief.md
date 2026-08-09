# Ruling needed: OQ-005 — Should an invalid `priority` value crash with a raw 500?

**What's being decided.** Sending a ticket-create request with a `priority` outside the accepted
set (not `low`/`med`/`high`/`1`/`2`/`3`) currently crashes with a raw, non-JSON Flask 500 — found
by the P9 adversarial audit, not in the original problem brief. Should the rewrite validate this
input properly (REPAIR), or carry the crash forward exactly (FIXED, current default)?

**Why it's ambiguous.**
- Reading A: Unsanctioned, unintended behavior. Every other validation failure in this app
  returns a proper JSON error (`422 title_required`, `429 rate_limited`, `403 invalid_token`) —
  this is the one path that doesn't, and nothing suggests that was deliberate.
- Reading B: No user ever reported this (it's absent from the handover notes); the contractor
  may have accepted "trust the client" here as a tradeoff for an internal tool nobody expected
  to send malformed input. Without testimony either way, it could be in-scope or out-of-scope.

**Where it bites.** `WO-001`, `docs/features/WO-001-tickets-core.md`'s two newest behavior
lines. `blocks: []` — doesn't block the WO from proceeding; WO-001 already carries the crash
forward as FIXED by default pending this ruling.

**Options & consequences.**
1. REPAIR (add validation, return `422` like the other fields) → better API behavior, one more
   PB entry to add retroactively so the change is properly sanctioned, small scope increase to
   WO-001.
2. FIXED (carry the crash forward exactly) → zero-risk from a fidelity standpoint (matches
   legacy byte-for-byte), ships an internal tool's raw-500 experience into the new stack too.
3. Defer → WO-001 proceeds under FIXED by default (already the case); revisit later via
   spec-patch.

**Recommendation (non-binding).** This and OQ-006 are close to a "free" fix — the same input-
validation pattern already exists for `title` (`422 title_required`); extending it to `priority`
is a small, low-risk change with an obvious shape. Worth ratifying as a REPAIR unless there's a
specific reason to preserve the crash.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
