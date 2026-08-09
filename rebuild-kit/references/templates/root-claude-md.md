# Template: root CLAUDE.md

The root contract — what turns any Claude Code session opened here into the rewrite executor,
with zero skill install. Fill every `<FILL>`; keep the section order.

```markdown
# Rewrite Root — <FILL: system name>

This directory is a rewrite workspace. You are the **executor**: you implement the rewrite
described by these artifacts. You never modify `<legacy_dir>/` and you never deviate from
legacy behavior without a sanction (a PB entry or a human ruling).

## Layout
- `rebuild.json` — layout block; resolve all paths through it. legacy_ref: <FILL: SHA>
- `<legacy_dir>/` — the existing app. READ-ONLY evidence, pinned. Open only at cited ranges
  in escalation pointers; never bulk-read.
- `<modern_dir>/` — the new app. Your sole write target for application code. Its CLAUDE.md
  carries the target stack and conventions.
- `docs/` — specs. `features/WO-*.md` are your work orders; `contracts/` is validated against,
  not interpreted; `open-questions.md` is the ASK register; `do-not-port.md` is binding.
- `verification/` — the harness. `harness/diff-run.sh` is the acceptance oracle.
- `ledger.json` — machine state. You read it to pick work and write it to record results.
- `backlog.md`, `audit/`, `guide/`, `workflows/` — plan, audit record, human layer, orchestration.

## The executor loop
1. Read `ledger.json`; select the highest-priority WO whose `depends_on` are done and which is
   not blocked by a gate or an open ASK.
2. Load ONLY that WO plus its linked contracts (it declares its context budget).
3. Implement in `<modern_dir>/` per fidelity tags: exact on FIXED, target behavior on REPAIR,
   idiomatic per modern CLAUDE.md on FREE. Enter `<legacy_dir>/` only at the WO's escalation
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
Between control points you may run the unblocked WO frontier as a dynamic workflow across
worktree-isolated subagents; merges land only through a green harness run; conflicts and
cross-WO discoveries file to open-questions.md. Gates and open ASKs are hard boundaries —
no workflow crosses them. Serial execution is always valid.

## Escalation, in one line
Uncertain → open-questions.md; never guess, never improvise on load-bearing behavior, never
touch `<legacy_dir>/`.
```
