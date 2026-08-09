# Ruling needed: OQ-005 — Timezone policy for datetime migration  **(BLOCKS WO-007)**

**What's being decided.** How to interpret legacy timestamps when moving them into
Postgres `timestamptz`.

**Why it's ambiguous.** The legacy code stamps tickets with `datetime.now().isoformat()` —
naive wall-clock time, no zone — and its own comment says so ("naive local time!",
`ticketd/app/server.py:52`). Meanwhile `reset_tokens.created_ts` uses `time.time()` —
epoch UTC (`ticketd/app/server.py:92`). The two tables disagree about what "now" means,
and nobody recorded what timezone the prod server runs in.

**Where it bites.** WO-007 (data migration) is **blocked** on this — converting years of
`created_at`/`closed_at` strings requires knowing their zone. Also touches WO-001's
serialization format choice and the list route's `ORDER BY created_at DESC` (a DST
fall-back hour can reorder naive strings).

**Options & consequences.**
1. "Prod runs in TZ X" (tell us X) → convert historical strings from X to UTC
   `timestamptz`; reconciliation R6 round-trips a sample to prove it.
2. Declare historical values UTC (if the server actually ran UTC) → simplest, same
   machinery.
3. Store naive `timestamp without time zone` forever → migration is a straight copy, but
   the new system inherits the ambiguity; not recommended.

**Recommendation (non-binding).** Check the prod host's `/etc/localtime` and rule option
1/2 accordingly — it's one fact, and everything else is mechanical.

---
Ruling: ____________  Ruled by: ________  Date: ______
