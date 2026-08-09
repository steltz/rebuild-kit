# Ruling needed: OQ-003 — Is the CSV export route (and its dead-code sibling) safe to drop?

**What's being decided.** `GET /internal/export/csv` and the never-imported
`legacy/app/legacy_import.py` both look dead by every static signal available. Should they be
dropped from the rewrite (do-not-port) or ported because something outside this codebase still
depends on them?

**Why it's ambiguous.**
- Reading A: Both are dead. The export route's own comment says "written for the 2020 audit; no
  caller since" (`legacy/app/server.py:112`); the importer's own docstring says "Nothing imports
  this module" (`legacy/app/legacy_import.py:1`); zero inbound references confirmed structurally
  (`inventory.json`).
- Reading B: An out-of-band consumer exists that this codebase can't show — a cron job, an
  external audit script, something outside this repo entirely. Cannot be ruled out without
  access logs, which don't exist for this run (`docs/problem-brief.md` OQ-INTAKE-02).

**Where it bites.** No WO depends on this ruling (`blocks: []` — flags gate review only), but
`WO-006` (the export route) sits unscheduled pending it, and `docs/do-not-port.md#DNP-001/002`
stay "candidate" rather than final until ruled either way.

**Options & consequences.**
1. Rule dead → delete `WO-006`, finalize both do-not-port entries, one less thing in the
   rewrite. If wrong, whatever depended on it breaks silently at cutover with no earlier warning
   from this codebase.
2. Rule live → `WO-006` gets built FIXED to current output shape (unescaped CSV bug included,
   as its own separate decision — see the WO for that nuance).
3. Defer → costs nothing; `WO-006` just stays unscheduled indefinitely, which is a legitimate
   steady state, not a blocker on anything else.

**Recommendation (non-binding).** This is the lowest-stakes ruling in the set — deferring
indefinitely is a real option, since nothing else depends on it. If a decision is wanted now,
the evidence (two independent "nobody calls this" comments plus zero structural references)
leans toward reading A.

---
Ruling: ____________  Ruled by: ________  Date: ______
(Recording the ruling in docs/open-questions.md triggers the spec-patch; this page re-renders.)
