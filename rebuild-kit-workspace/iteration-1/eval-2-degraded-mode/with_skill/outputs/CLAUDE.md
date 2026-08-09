# Rewrite Root — ticketd

This directory is a rewrite workspace. You are the **executor**: you implement the rewrite
described by these artifacts. You never modify `ticketd/` and you never deviate from
legacy behavior without a sanction (a PB entry or a human ruling).

## Layout
- `rebuild.json` — layout block; resolve all paths through it.
  legacy_ref: `tree-02fcc10c238482f7672caacb333b91cb3a84e39d0262868efad28f3e524fc0a3`
  (unversioned snapshot — the contractor handover carried no git history; the pin is a content
  hash of the tree, recomputable via `scripts/` staleness check if an upstream copy appears).
- `ticketd/` — the existing app (Flask 1.x era, SQLite). READ-ONLY evidence, pinned. Open only
  at cited ranges in escalation pointers; never bulk-read.
- `modern/` — the new app (FastAPI + Postgres). Your sole write target for application code.
  Its CLAUDE.md carries the target stack and conventions.
- `docs/` — specs. `features/WO-*.md` are your work orders; `contracts/` is validated against,
  not interpreted; `open-questions.md` is the ASK register; `do-not-port.md` is binding.
- `verification/` — the harness. `harness/diff-run.sh` is the acceptance oracle.
- `ledger.json` — machine state. You read it to pick work and write it to record results.
- `backlog.md`, `audit/`, `guide/`, `workflows/` — plan, audit record, human layer, orchestration.

## Degraded-mode notice — read before trusting any spec
This workspace was generated **code-only**. There is no git history, no production logs or APM,
and no production database access (`rebuild.json.evidence` records all three subsystems
inactive). Consequences you must respect:
- No claim in any spec is backed by observed production traffic. Confidence is capped at
  `code-derived`; usage weights are structural estimates, not measurements.
- Replay evidence is **T2** (scripted sessions through the twin-boot harness) and **T3**
  (statically derived pairs, provisional). There are no T1 production traces.
- Migration planning in `docs/migration/` is written against the DDL only; the data census is
  deferred until DB access arrives (tracked as OQ entries). **M3 (migration) is gated on it.**
- When production evidence arrives, a spec-patch session (the rebuild-kit skill in resume mode)
  layers it in. Do not upgrade confidence labels yourself.

## The executor loop
1. Read `ledger.json`; select the highest-priority WO whose `depends_on` are done and which is
   not blocked by a gate or an open ASK.
2. Load ONLY that WO plus its linked contracts (it declares its context budget).
3. Implement in `modern/` per fidelity tags: exact on FIXED, target behavior on REPAIR,
   idiomatic per modern CLAUDE.md on FREE. Enter `ticketd/` only at the WO's escalation
   pointers.
4. Run L1 + L2 locally; run the WO's replay set through the twin-boot harness (L3), expected
   divergences included.
5. Green: mark done in the ledger, record FREE choices made, commit.
6. Red: fix the implementation. If the SPEC appears wrong — or you believe an unsanctioned
   legacy behavior should change — never act silently: file it to `docs/open-questions.md`
   (discrepancy or PB proposal), generate its ruling brief into `guide/briefs/`, set the WO
   `awaiting_ruling` if blocked. Continue elsewhere.
7. Gate WOs (`gate: true`): STOP. Emit the gate packet to `guide/briefs/`, request human
   sign-off; the ledger records approver and timestamp before the WO closes.
8. Milestone close: full-suite regression replay + human review of any new expected-divergence
   entries; refresh the guide's as-built pages; then start the next milestone.

## Parallel execution (optional, scale permitting)
This target is small (~170 lines of legacy code). Serial execution is the expected mode; the
workflow machinery under `workflows/` exists for regeneration, not day-to-day execution.
Gates and open ASKs are hard boundaries regardless.

## Escalation, in one line
Uncertain → open-questions.md; never guess, never improvise on load-bearing behavior, never
touch `ticketd/`.
