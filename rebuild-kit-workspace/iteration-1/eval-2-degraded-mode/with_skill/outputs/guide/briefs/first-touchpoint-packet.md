# First touchpoint — everything the owner owes this workspace (one sitting)

Generated 2026-08-08; the owner was unreachable during generation. Until this page is
worked through, execution can proceed only to the edge of M0.

1. **Sign the expected-divergence manifest** (verification/replay/expected-divergences.yaml,
   9 entries, all `ruled_by: PENDING`). This ratifies: queued email dispatch (ED-001/002/
   002b ← PB-001), hashed CSPRNG reset tokens (ED-003 ← PB-002), and 422s for four
   garbage-input 500s (ED-004a/b). Nothing diverges from legacy without your signature —
   the differ enforces it.
2. **Confirm the problem brief** (docs/problem-brief.md): severities of PB-001/PB-002
   (OQ-INT-1), and add anything the handover notes missed.
3. **Rule the three cheap questions** — briefs in this directory: OQ-001 (CSV export
   dead?), OQ-002 (what consumes reset? — highest leverage), OQ-004 (bypass header
   keep/kill). OQ-003 can wait.
4. **State NFRs and non-goals if any exist** (OQ-INT-3) — currently none are recorded and
   none were invented.
5. **When DB access lands** (OQ-INT-2): grant a read-only connection, have
   docs/migration/census-queries.sql run, then open a session with the rebuild-kit skill at
   this root — it routes to spec-patch mode and folds the results in. Same procedure when
   access logs appear: usage-weights.json upgrades from static-proxy to observed.

Approve M0 gate after WO-001: guide/briefs/gate-M0.md will be emitted by the executor with
the harness report attached.
