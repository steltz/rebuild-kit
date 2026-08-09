# Ruling needed: OQ-001 — Is /internal/export/csv still consumed by anything?

**What's being decided.** Whether the CSV export route (all tickets as unescaped
`id,title,status` lines) is ported to the new system or deleted.

**Why it's ambiguous.**
- Reading A: dead — code comment "written for the 2020 audit; no caller since"
  (ticketd/app/server.py:112); nothing else references it.
- Reading B: alive — no access logs exist in this handover, so zero traffic cannot be
  demonstrated; the route is reachable and unauthenticated.

**Where it bites.** Blocks WO-007 only. Usage estimate 0.01 (structural guess).

**Options & consequences.**
1. Rule dead → WO-007 cancelled, DNP-002 activates, one less unauthenticated route.
2. Rule live → format frozen byte-for-byte (broken comma-escaping included — its consumer
   has parsed exactly this since 2020).
3. Defer → WO-007 stays blocked; harmless until M2.

**Recommendation (non-binding).** Rule dead unless you know the audit tool still runs;
the comment is contemporaneous testimony and nothing else references the route.

---
Ruling: ____________  Ruled by: ________  Date: ______
