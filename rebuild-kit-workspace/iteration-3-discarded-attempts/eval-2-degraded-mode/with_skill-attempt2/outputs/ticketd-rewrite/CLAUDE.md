# Rewrite Root — ticketd

This directory is a rewrite workspace. You are the **executor**: you implement the rewrite
described by these artifacts. You never modify `legacy/` and you never deviate from legacy
behavior without a sanction (a PB entry or a human ruling).

**Context for this workspace:** generated non-interactively, without the contractor who wrote
`legacy/` and without production access. Two known defects seeded the problem brief
(`docs/problem-brief.md`: PB-001 sync email, PB-002 MD5 reset tokens). Runtime evidence (P2),
data census (P6), and trace capture (P7 T1) are all **inactive** — see `rebuild.json.evidence`.
Every behavior claim in this workspace is sourced from static code reading of `legacy/` only;
T3 (statically derived) tier, never T1/T2, unless a later spec-patch upgrades it. Treat specs
here as a well-evidenced first pass, not a finished audit — confirm against real usage once
production DB/log access lands (tracked as OQ-007 in `docs/open-questions.md`).

## Layout
- `rebuild.json` — layout block; resolve all paths through it.
  legacy_ref: `tree-02fcc10c238482f7672caacb333b91cb3a84e39d0262868efad28f3e524fc0a3`
  (unversioned-snapshot — legacy had no git history at intake, so the pin is a content hash of
  the whole tree, not a commit SHA. `scripts/staleness_check.py` re-hashes to detect drift.)
- `legacy/` — the existing app (Flask + sqlite). READ-ONLY evidence, pinned. Open only at cited
  ranges in escalation pointers; never bulk-read. Enforced two ways: filesystem permissions
  (write bits stripped at scaffold time) and a pre-commit hook (`.githooks/pre-commit`) that
  rejects any staged diff under `legacy/`. Both were verified during P0.
- `modern/` — the new app (FastAPI + Postgres). Your sole write target for application code. Its
  CLAUDE.md carries the target stack and conventions.
- `docs/` — specs. `features/WO-*.md` are your work orders; `contracts/` is validated against,
  not interpreted; `open-questions.md` is the ASK register (6 generator-raised OQs already
  seeded from intake gaps — read it before assuming anything not in a PB); `do-not-port.md` is
  binding.
- `verification/` — the harness. `harness/diff-run.sh` is the acceptance oracle. Because trace
  capture is inactive, the replay corpus is T2/T3 (scripted + statically derived), not captured
  production traffic — every replay-backed WO says so explicitly.
- `ledger.json` — machine state. You read it to pick work and write it to record results.
- `backlog.md`, `audit/`, `guide/`, `workflows/` — plan, audit record, human layer, orchestration.

## The executor loop
1. Read `ledger.json`; select the highest-priority WO whose `depends_on` are done and which is
   not blocked by a gate or an open ASK.
2. Load ONLY that WO plus its linked contracts (it declares its context budget).
3. Implement in `modern/` per fidelity tags: exact on FIXED, target behavior on REPAIR, idiomatic
   per modern CLAUDE.md on FREE. Enter `legacy/` only at the WO's escalation pointers.
4. Run L1 + L2 locally; run the WO's replay set through the twin-boot harness (L3), expected
   divergences included. Remember: with T1 inactive, L3 coverage is thinner than a
   fully-evidenced rewrite — do not treat a green T3-derived replay as equivalent to a
   production-traffic-verified one.
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
Between control points you may run the unblocked WO frontier as a dynamic workflow across
worktree-isolated subagents; merges land only through a green harness run; conflicts and cross-WO
discoveries file to open-questions.md. Gates and open ASKs are hard boundaries — no workflow
crosses them. Serial execution is always valid, and given this app's size (5 legacy source files,
3 tables), serial execution is expected to be the normal path.

## Escalation, in one line
Uncertain → open-questions.md; never guess, never improvise on load-bearing behavior, never touch
`legacy/`. When evidence is thin (which is the default state of this workspace), prefer opening
an OQ over silently trusting an inferred claim.
