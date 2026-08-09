# WO-008 — Migration tooling (transform + reconciliation runner)

id: WO-008            depends_on: [WO-001]    milestone: M3
risk: 0.55 (data-shape assumptions unvalidated — census pending; TZ policy is ASK)
gate: false (the gated step is WO-009's rehearsal)
usage_weight: n/a   pain_weight: 0.3 (PB-003 implies it; data loss risk concentrates here)
context_budget: ~350 lines (this WO + docs/migration/mapping.md + reconciliation.sql +
  census.md)

behaviors:
  - statement: Transform implements docs/migration/mapping.md exactly: identity-carry for
      tickets/users, sequence bump, enum casts, naive-localtime → UTC conversion
      parameterized by the ratified source timezone, reset_tokens per ratified policy.
      Every ASK-marked policy in mapping.md must hold a ratified value before this runs
      against real data — the tool must refuse to run with unratified policies.
    fidelity: FIXED (mapping is the contract) — policies themselves are ASK until ratified
    evidence: [docs/migration/mapping.md, docs/contracts/ddl.sql]
  - statement: Reconciliation runner executes docs/migration/reconciliation.sql (R1-R8) and
      emits a machine-readable pass/fail report; any red = migration WO fails.
    fidelity: FIXED
    evidence: [docs/migration/reconciliation.sql]
  - statement: Dirty rows are never silently repaired or dropped — each ratified policy's
      actions are logged with counts; quarantined rows land in side tables.
    fidelity: FIXED (P6 rule: data destruction is never silent)
    evidence: [docs/migration/census.md]
  - statement: Tool structure, language, invocation.
    fidelity: FREE — record in ledger free_choices.

acceptance:
  replay_set: n/a (data workstream)
  tests: transform+reconciliation green on a synthetic dirty dataset that exercises every
    census probe class (build the dataset as part of this WO; include dangling assignee_id,
    out-of-vocab priority, comma titles, expired tokens)
escalation: none (no legacy code beyond DDL is involved)
