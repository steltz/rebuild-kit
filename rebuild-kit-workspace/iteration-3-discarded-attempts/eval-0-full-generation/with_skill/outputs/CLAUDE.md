# Rewrite Root — ticketd

This directory is a rewrite workspace. You are the **executor**: you implement the rewrite
described by these artifacts. You never modify `legacy/` and you never deviate from legacy
behavior without a sanction (a PB entry or a human ruling).

## Layout
- `rebuild.json` — layout block; resolve all paths through it.
  legacy_ref: `1cc113597ea87990e731f02190fc6999e42e7cd8`
- `legacy/` — the existing Flask/SQLite ticket tracker. READ-ONLY evidence, pinned. Open only at
  cited ranges in escalation pointers; never bulk-read. `legacy/` carries its own `.git` (it was
  pinned via `sha-recorded-clone`, not a submodule gitlink) — the pre-commit hook in
  `.githooks/pre-commit` blocks both file-level changes under `legacy/` and gitlink-level commits
  of the embedded repo itself.
- `modern/` — the new FastAPI + PostgreSQL app. Your sole write target for application code. Its
  `CLAUDE.md` carries the target stack and conventions.
- `docs/` — specs. `features/WO-*.md` are your work orders; `contracts/` is validated against,
  not interpreted; `open-questions.md` is the ASK register; `do-not-port.md` is binding.
- `verification/` — the harness. `harness/diff-run.sh` is the acceptance oracle.
- `ledger.json` — machine state. You read it to pick work and write it to record results.
- `backlog.md`, `audit/`, `guide/`, `workflows/` — plan, audit record, human layer, orchestration.

## Known evidence gaps (read before trusting usage/perf numbers)
- `ops/access.log` (now `legacy/ops/access.log`) was described as a ~30-day log but is actually
  one synthetic hour, one user, one user-agent (OQ-102 in `docs/open-questions.md`). Usage
  weights and perf envelopes derived from it (`usage-weights.json`, `perf-envelopes.json`) are
  directional only — don't treat backlog ordering as validated against real production traffic.
- No incident trace exists for the June SMTP outage that motivated this rewrite (OQ-101); the
  REPAIR target for WO-002 is justified from source evidence alone, which is sufficient, but
  don't expect a trace to replay against for that specific incident.
- No production DB access was available this run — `docs/migration/census.md` ships as
  DDL-derived queries a human still needs to run (P6 degraded mode); `rebuild.json.evidence.
  data_census` is `inactive`.

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

## Parallel execution (optional, scale permitting)
This is a 4-file, ~200-line legacy app — most milestones are small enough to execute serially in
one session. Between control points you *may* run the unblocked WO frontier as a dynamic workflow
across worktree-isolated subagents if it's genuinely useful, but don't reach for orchestration
machinery this app doesn't need. Merges land only through a green harness run; conflicts and
cross-WO discoveries file to `open-questions.md`. Gates and open ASKs are hard boundaries — no
workflow crosses them.

## Escalation, in one line
Uncertain → `open-questions.md`; never guess, never improvise on load-bearing behavior, never
touch `legacy/`.
