# Ruling needed: OQ-003 — Drop `GET /internal/export/csv`?

**What's being decided.** Whether the audit-era CSV export is rebuilt or retired.

**Why it's ambiguous.**
- Dead: source comment "written for the 2020 audit; no caller since"
  (`ticketd/app/server.py:112`); zero traffic in the 30-day log (`zero-traffic.md`).
- Maybe-alive: it was written for an *annual* audit — a 30-day window can't see yearly use.

**Where it bites.** Nothing is blocked — it's simply not scheduled (DNP-001). The decision
must land **before cutover** (WO-008): after cutover, the endpoint 404s.

**Options & consequences.**
1. Ratify the drop → zero work; if an auditor needs a dump later, `psql \copy` does more
   than this endpoint ever did.
2. Keep → new WO via spec-patch; also decide whether to keep its unescaped-comma CSV bug
   (`ticketd/app/server.py:114`) bug-for-bug or repair it (needs a PB entry either way).
3. Defer to cutover gate → fine, it's on that gate's checklist (`docs/migration/cutover.md`).

**Recommendation (non-binding).** Ask whoever ran the 2020 audit; absent testimony, ratify
the drop — option 1.

---
Ruling: ____________  Ruled by: ________  Date: ______
