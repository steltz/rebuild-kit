# WO-008 — Migration rehearsal & cutover

id: WO-008            depends_on: [WO-007]          milestone: M3
risk: 0.60 (human-owned execution; risk is coordination, not code)
usage_weight: —       pain_weight: —                context_budget: ~200 lines   gate: true

Reading list: this file · `docs/migration/cutover.md` · `docs/migration/reconciliation.sql`.

This WO is mostly a human checklist (docs/migration/cutover.md); the executor's share:

behaviors:
  - statement: full dry run — census on the prod snapshot, ratified policies applied,
      loader run, reconciliation green, then a FULL L3 regression (t2-core + any sets added
      since) with the migrated snapshot as the modern seed.
    fidelity: FREE — mechanics per cutover.md; outcomes are the listed checks.
  - statement: cutover sequence + rollback window per cutover.md, executed by humans;
      executor prepares the smoke subset (read-only traces) and the switch/rollback scripts.
    fidelity: FREE — with the constraint that rollback keeps legacy untouched (cutover.md).

acceptance:
  gate: human sign-off on the rehearsal results packet (guide/briefs/WO-008-gate-packet.md,
    generated when this WO halts) — reconciliation output, regression report, census counts
    with ratified policies, rollback plan with a decided observation window.
escalation: none — this order is executed WITH the humans, not for them.
