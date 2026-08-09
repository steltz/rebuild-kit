id: WO-005            depends_on: [WO-001]                 milestone: M1
risk: 0.6 (PB severity medium; but ASK density HIGH -- the core mechanism is blocked on OQ-001,
  which is currently PENDING; complexity low once ruled; legacy coverage none)
usage_weight: 0.2115 (shares POST /api/tickets' usage weight -- this WO modifies that route's
  behavior, not a separate route)
pain_weight: 0.5 (PB-003, severity medium, recurring support complaint)
context_budget: ~300 lines (this WO + docs/open-questions.md OQ-001 + docs/migration/mapping.md
  slug section + docs/migration/census.md probe #26/#27)
gate: true (blocked_by_asks: [OQ-001] -- cannot close without a ruling; this alone forces gate
  status regardless of the numeric risk score, per root CLAUDE.md's executor loop step 1)

## What this WO does
Enforce `tickets.slug` uniqueness (currently unenforced anywhere -- no DB constraint, no app
check) and resolve new-ticket slug collisions per whatever OQ-001 rules.

**THIS WO CANNOT CLOSE WITHOUT A HUMAN RULING ON OQ-001.** If picked up while OQ-001 is still
PENDING, per root CLAUDE.md's executor loop: skip it, continue elsewhere, do not improvise a
mechanism. Reading the three options in OQ-001 for orientation is fine; choosing one without a
ruling is not.

behaviors:
  - statement: "tickets.slug must be unique at the database level."
    fidelity: REPAIR — outcome ratified by PB-003 (this much is NOT ambiguous: "nobody has
      decided what the fix should be" was about the RESOLUTION mechanism, not about whether
      uniqueness itself is desired -- support hitting collisions is the named problem).
    evidence: [docs/problem-brief.md PB-003, legacy/app/util.py:4-6, legacy/db/schema.sql:1-10
      (no UNIQUE constraint on slug)]
  - statement: "What happens when a new ticket's computed slug collides with an existing one:
      reject-and-ask-client-to-disambiguate (422) vs. auto-suffix (fix-db-2) vs.
      include-the-id-in-every-slug (fix-db-1042)."
    fidelity: ASK — OQ-001, PENDING. This WO is blocked on this ruling; do not pick option B
      (auto-suffix) as a 'safe default' without ratification -- schema.md's fidelity taxonomy
      exists precisely to prevent an executor quietly resolving this on its own judgment.
    evidence: [docs/open-questions.md OQ-001]
  - statement: "Pre-existing collisions in production data (if any) need a backfill policy
      before a UNIQUE constraint can even be added -- census.md probe #26/#27 are currently
      unrun (no prod DB access granted)."
    fidelity: ASK — blocked on data census access AND on OQ-001 (the backfill policy and the
      new-collision policy are related decisions, likely made together).
    evidence: [docs/migration/census.md, docs/migration/mapping.md]

acceptance:
  replay_set: tickets-create-007/008 (slug-collision-a/b, already captured as T2 golden) --
    NOTE these traces currently assert LEGACY's collision-permitting behavior (both succeed
    with the same slug, 201/201). Once OQ-001 rules a mechanism, this WO must ALSO update
    these traces' expected outcome (or add new ones) to reflect the RULED behavior -- the
    existing goldens are a starting point, not a frozen target, for exactly the two entries
    this WO changes. Everything else in tickets-create-*.jsonl stays FIXED.
  tests: characterization/tickets/slug-uniqueness.spec (new, written once OQ-001 rules)
  l1: n/a (no new route; may add a new error response shape to POST /api/tickets depending on
    the ruling -- update docs/contracts/openapi.yaml if so)
  l3: verification/harness/diff-run.sh tickets-create (re-run after golden refresh)

escalation: legacy/app/util.py (7 lines) is the entire current mechanism; nothing else to
  escalate to until OQ-001 rules.
