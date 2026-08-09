# Ruling needed: OQ-002 — What delivery guarantee does the async email fix need?

**What's being decided.** PB-001's fix moves email dispatch off the request path. That leaves
open: if the async dispatch mechanism itself fails (process restart, worker crash), should the
email be retried until it succeeds (durable outbox), or is best-effort — send once, don't retry —
acceptable, matching legacy's own lack of retry logic?

**Why it's ambiguous.**
- Reading A: At-least-once via a durable outbox + worker — survives restarts, retries on
  failure. Justified if watcher notifications / reset-token delivery are business-critical.
  evidence: the original blocking behavior (`legacy/app/server.py:75-76`) suggests outage
  sensitivity was already a known pain point, but there's no data on how often SMTP actually
  fails in production (no APM — `docs/problem-brief.md` OQ-INTAKE-02).
- Reading B: Best-effort via an in-process background task, at-most-once, no retry — legacy
  itself never retried either (a single unretried `send_mail` call), so REPAIR only needs to
  remove the blocking, not add a reliability guarantee nothing asked for.

**Where it bites.** Affected flows: `guide/flows/password-reset.md` (request step) and ticket
close (`guide/legacy/tickets.md`). Blocks: `WO-004` (the dispatch infrastructure itself), which
in turn blocks `WO-002` and `WO-003`. This is the single highest-leverage ruling in the
backlog — nothing in M1 can close without it.

**Options & consequences.**
1. Durable outbox (at-least-once) → more infrastructure (a table + worker or a queue), stronger
   guarantee, appropriate if losing a notification silently would be a real problem.
2. Background task (best-effort) → less infrastructure, ships faster, matches legacy's own
   reliability level exactly (no regression, but no improvement on that axis either).
3. Defer → M1 stays blocked entirely; nothing in tickets-close or auth-reset can be built past
   what M0 already covers.

**Recommendation (non-binding).** Best-effort (reading B) is the smaller change and matches
what PB-001 actually asked for — "don't block the request," not "guarantee delivery." Upgrading
to a durable outbox later, once real failure-rate data exists (post OQ-INTAKE-02), is a lower-
risk sequencing than over-building now on no evidence.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
