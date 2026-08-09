# Open Questions — ASK register & PB proposals

<!-- Executor + generator both append here. Never delete entries; rulings are appended.
     Each new OQ gets a ruling brief generated into guide/briefs/. -->

## OQ-001 — Is /internal/export/csv still consumed by anything?
- raised_by: generator P4
- kind: inferred-only (dead-route candidate without runtime corroboration)
- readings:
  - A: dead since 2020 — evidence: in-code comment "written for the 2020 audit; no caller
    since" (ticketd/app/server.py:112); zero references elsewhere in the tree
  - B: still called by an external audit tool — evidence: none possible; NO access logs exist
    (degraded mode), so zero-traffic cannot be shown
- blocks: [WO-007]
- ruling: PENDING
  <!-- If dead: WO-007 is cancelled and the route moves to do-not-port (DNP-002 activates).
       If live: WO-007 ports the format byte-for-byte, unescaped commas and all. -->

## OQ-002 — What consumes a confirmed password reset? (users table is orphaned)
- raised_by: generator P3/P4
- kind: ambiguity
- readings:
  - A: an external auth system calls confirm and uses the echoed email to reset a password it
    stores — evidence: confirm returns `{"ok": true, "email": ...}` (ticketd/app/server.py:108),
    yet no login endpoint or password column exists anywhere (ticketd/db/schema.sql:12-16)
  - B: the flow is vestigial (the contractor removed login but left reset) — evidence: `users`
    is read/written by no code path; reset never validates email against users
    (ticketd/app/server.py:82-95)
- blocks: [] (WO-006 implements observed behavior either way; flags M2 gate review — if B,
  the owner may cancel WO-006 entirely)
- ruling: PENDING

## OQ-003 — Slug: is collision-freedom or any read path expected?
- raised_by: generator P4
- kind: inferred-only
- readings:
  - A: slug is decorative/vestigial — evidence: no route reads or queries by slug; not UNIQUE
    (ticketd/db/schema.sql:4); collisions acknowledged in ticketd/app/util.py:5
  - B: some client (the UI?) uses slug from list/create responses for display or URLs and
    expects the exact derivation — evidence: slug is included in both responses
    (ticketd/app/server.py:37,55)
- blocks: [] (WO-003 ports the derivation exactly, which satisfies both readings; a ruling
  would only permit cleanup)
- ruling: PENDING

## OQ-004 — X-Internal-Bypass rate-limit header: load-bearing or backdoor?
- raised_by: generator P4
- kind: ambiguity
- readings:
  - A: an internal tool (bulk admin? test rig) depends on it — evidence: it was written
    deliberately with an exact-match check (ticketd/app/server.py:84)
  - B: contractor debugging leftover; it is an unauthenticated bypass anyone can send —
    evidence: in-code comment "undocumented bypass header" (ticketd/app/server.py:84); no
    other reference in the tree
- blocks: [] (WO-006 implements parity behind config flag `RESET_RATE_LIMIT_BYPASS_ENABLED`,
  default ON for replay parity; flags M2 gate review for the kill decision)
- ruling: PENDING

## OQ-INT-1 — Intake gap: severities/impact of PB-001 and PB-002 unconfirmed
- raised_by: generator P0 (non-interactive intake; owner unreachable during generation)
- kind: inferred-only
- readings: severity "high" for both PBs is inferred from handover phrasing and security
  common sense; no incident history or logs exist to confirm.
- blocks: [] (repairs proceed regardless; severity affects only backlog emphasis)
- ruling: PENDING (owner confirms or adjusts at first touchpoint)

## OQ-INT-2 — Production DB access (expected "in a few weeks")
- raised_by: generator P0
- kind: inferred-only (data census impossible until granted)
- readings: row counts, dirty-data reality (dangling assignee_id under the unenforced FK,
  naive-localtime skew, expired-token volume, CHECK-violating rows written before constraints)
  are all unknown; docs/migration/census.md holds ready-to-run queries.
- blocks: [WO-009] (migration execution; M3 gate)
- ruling: PENDING (becomes a spec-patch run: execute census, update migration docs)

## OQ-INT-3 — Intake gaps: NFRs, non-goals, export consumer, bypass-header owner
- raised_by: generator P0
- kind: inferred-only
- readings: no SLOs/scale targets, no non-goals list, and the OQ-001/OQ-004 questions need
  owner memory. One interview closes this plus OQ-001/OQ-004 and likely OQ-002.
- blocks: []
- ruling: PENDING
