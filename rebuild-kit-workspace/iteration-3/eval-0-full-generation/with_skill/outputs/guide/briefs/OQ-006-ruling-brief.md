# Ruling needed: OQ-006 — Should ticket timestamps move from naive-local to UTC-aware?

**What's being decided.** `tickets.created_at`/`closed_at` are stored as naive local timestamps
(`datetime.now().isoformat()`, no timezone) — even the original developer flagged this as
suspect in an inline code comment. Should the rewrite fix this, or preserve it as-is?

**Why it's ambiguous.** Nobody reported this as a problem in the intake that commissioned this
rewrite — it surfaces only from the code's own admission. PB-006 (no UI changes) implies no
client-visible contract should shift without cause, but a generator-level read of the code
believes this is a latent correctness issue worth fixing.

**Where it bites.** Affected: ticket create/close (`guide/legacy/tickets.md`). Blocks: WO-005
(data migration) can't fully close without this ruling — it determines whether `created_at`/
`closed_at` become Postgres `TIMESTAMPTZ` or plain `TIMESTAMP`. Also entangled with **OQ-009**
(what timezone did legacy actually run in) — a `TIMESTAMPTZ` conversion needs that answer
regardless of how this one is ruled.

**Options & consequences.**
1. **REPAIR to UTC-aware `timestamptz`.** Correct, and Postgres makes it nearly free — but
   requires answering OQ-009 first (can't convert naive-local to UTC without knowing what "local"
   meant), and is a real, if invisible-to-most-clients, behavior change.
2. **Preserve naive-local-time-equivalent semantics.** Zero risk, zero new questions, matches
   "nobody asked for this" — but ships a known, admitted defect forward on purpose.

**Recommendation (non-binding).** Low urgency, low risk either way — this is exactly the kind of
thing worth batching with OQ-009 into one conversation rather than ruling in isolation, since
option 1 is worthless without OQ-009's answer anyway.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
