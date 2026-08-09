# Rewrite Root — ticketd

This directory is a rewrite workspace. You are the **executor**: you implement the rewrite
described by these artifacts. You never modify `legacy/` and you never deviate from legacy
behavior without a sanction (a PB entry or a human ruling).

**Generated in degraded mode.** No git history, no access logs/APM, no production database
access were available when this workspace was generated (they may arrive in a few weeks). See
`rebuild.json.evidence` for exactly what is active/inactive and what that caps. Re-run this
skill in spec-patch mode once evidence arrives — see `references/phases/spec-patch.md` in the
skill, or just bring the human ruling / new evidence to a fresh session at this root.

## Layout
- `rebuild.json` — layout block; resolve all paths through it. `legacy_ref`:
  `tree-02fcc10c238482f7672caacb333b91cb3a84e39d0262868efad28f3e524fc0a3` (content hash — the
  legacy tree shipped with no git history, see `rebuild.json.legacy_pin_note`).
- `legacy/` — the existing app. READ-ONLY evidence, pinned. Open only at cited ranges in
  escalation pointers; never bulk-read. (It happens to be small enough — four Python files — that
  the temptation to just read it all is real; resist it anyway, the discipline is the point.)
- `modern/` — the new app. Your sole write target for application code. Its CLAUDE.md carries
  the target stack (FastAPI + PostgreSQL) and conventions.
- `docs/` — specs. `features/WO-*.md` are your work orders; `contracts/` is validated against,
  not interpreted; `open-questions.md` is the ASK register (includes PB-proposals for
  code-observed oddities nobody reported — see below); `do-not-port.md` is binding.
- `verification/` — the harness. `harness/diff-run.sh` is the acceptance oracle. Legacy actually
  boots locally here (Flask + sqlite3, no external services required except SMTP, which is
  stubbed for replay — see `verification/harness/README.md`), so L3 is live, not aspirational,
  despite the evidence gaps above.
- `ledger.json` — machine state. You read it to pick work and write it to record results.
- `backlog.md`, `audit/`, `guide/`, `workflows/` — plan, audit record, human layer, orchestration.

## The executor loop
1. Read `ledger.json`; select the highest-priority WO whose `depends_on` are done and which is
   not blocked by a gate or an open ASK.
2. Load ONLY that WO plus its linked contracts (it declares its context budget).
3. Implement in `modern/` per fidelity tags: exact on FIXED, target behavior on REPAIR, idiomatic
   per `modern/CLAUDE.md` on FREE. Enter `legacy/` only at the WO's escalation pointers.
4. Run L1 + L2 locally; run the WO's replay set through the twin-boot harness (L3), expected
   divergences included.
5. Green: mark done in the ledger, record FREE choices made, commit.
6. Red: fix the implementation. If the SPEC appears wrong — or you believe an unsanctioned legacy
   behavior should change — never act silently: file it to `docs/open-questions.md` (discrepancy
   or PB proposal), generate its ruling brief into `guide/briefs/`, set the WO `awaiting_ruling`
   if blocked. Continue elsewhere.
7. Gate WOs (`gate: true`): STOP. Emit the gate packet to `guide/briefs/`, request human
   sign-off; the ledger records approver and timestamp before the WO closes.
8. Milestone close: full-suite regression replay + human review of any new expected-divergence
   entries; refresh the guide's as-built pages; then start the next milestone.

## Degraded-mode caveats the executor must respect
- Usage/pain ordering in `backlog.md` uses a **static proxy** (route count x inbound-reference
  count), not real traffic. Don't treat WO order as a traffic-validated priority — it's a
  reasonable guess pending P2.
- `docs/migration/mapping.md` dirty-data policies are **all ASK** — nothing is ratified because
  no prod-shaped data has been queried yet. Do not implement a migration WO's transform without
  a ruling on its policy.
- Perf envelopes do not exist. No NFR latency/throughput floor is enforced by the harness.
- T1 (captured production traffic) is absent from every replay set; T2 (scripted, but against a
  really-booted legacy) and T3 (statically derived, provisional) are what you have. T3-only
  coverage counts toward L2, never L3 — check `acceptance.replay_set` tiers per WO before trusting
  an L3 "pass" fully.

## Parallel execution (optional, scale permitting)
Between control points you may run the unblocked WO frontier as a dynamic workflow across
worktree-isolated subagents; merges land only through a green harness run; conflicts and cross-WO
discoveries file to open-questions.md. Gates and open ASKs are hard boundaries — no workflow
crosses them. Serial execution is always valid, and given this app's size (4 legacy files, 6
routes), serial is almost certainly the right call — see the skill's proportionality rule.

## Escalation, in one line
Uncertain → open-questions.md; never guess, never improvise on load-bearing behavior, never touch
`legacy/`.
