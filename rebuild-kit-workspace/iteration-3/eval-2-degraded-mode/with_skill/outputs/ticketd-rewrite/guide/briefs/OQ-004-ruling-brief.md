# Ruling needed: OQ-004 — Is `users`/`assignee_id` a dead feature or a missing route?

**What's being decided.** The schema has a `users` table and `tickets.assignee_id`, but no route
anywhere reads or writes either. Was ticket assignment planned but never shipped in this
codebase, or does it exist somewhere this handover didn't include?

**Why it's ambiguous.**
- Reading A: Planned but never shipped, in this codebase. Port the schema shape (structure only,
  FREE) but treat assignment as out of scope — no behavior exists to characterize.
- Reading B: An assignment feature exists elsewhere (a second service, an admin script not in
  this handover) that just isn't in `legacy/`. Can't be ruled out — no git history, no other
  source tree was provided alongside this one.

**Where it bites.** No WO depends on this (`blocks: []`) — it only flags gate review. Affects
`WO-001`'s schema-carry-forward choice and `WO-005`'s migration mapping, both of which currently
assume reading A (no real behavior to migrate); also affects `docs/migration/mapping.md`'s
FK-enforcement note (Postgres enforces `assignee_id → users.id` by default, SQLite doesn't — a
P9 audit finding in `docs/domain/ticket.md`) if reading B turns out true and real assignee data
exists.

**Options & consequences.**
1. Confirm reading A → no further action needed; current WOs already assume this.
2. Confirm reading B (a feature exists elsewhere) → this handover is incomplete; the rewrite
   scope may need to expand to cover whatever that other system does, which is outside what this
   workspace can plan for without seeing it.
3. Defer → current WOs proceed under reading A by default; low risk, since the schema shape is
   carried forward regardless of which reading is true.

**Recommendation (non-binding).** Proceed under reading A (no action needed) unless there's
independent knowledge of a second system — this codebase alone cannot distinguish the two
readings, and reading A is the safer default since it doesn't require inventing behavior that
might not exist.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
