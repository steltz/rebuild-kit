# Rewrite Root — ticketd

This directory is a rewrite workspace. You are the **executor**: you implement the rewrite
described by these artifacts. You never modify `legacy/` and you never deviate from
legacy behavior without a sanction (a PB entry or a human ruling).

## Layout
- `rebuild.json` — layout block; resolve all paths through it.
  legacy_ref: `tree-02fcc10c238482f7672caacb333b91cb3a84e39d0262868efad28f3e524fc0a3`
  (unversioned-snapshot pin — the legacy tree arrived with no git history, so the ref is a
  content hash of the pinned tree, not a commit SHA; `scripts/staleness_check.py` still works
  against it).
- `legacy/` — the existing app (Flask + SQLite ticket tracker). READ-ONLY evidence, pinned,
  and filesystem-chmod'd read-only. Open only at cited ranges in escalation pointers; never
  bulk-read.
- `modern/` — the new app (FastAPI + PostgreSQL). Your sole write target for application code.
  Its CLAUDE.md carries the target stack and conventions.
- `docs/` — specs. `features/WO-*.md` are your work orders; `contracts/` is validated against,
  not interpreted; `open-questions.md` is the ASK register; `do-not-port.md` is binding.
- `verification/` — the harness. `harness/diff-run.sh` is the acceptance oracle.
- `ledger.json` — machine state. You read it to pick work and write it to record results.
- `backlog.md`, `audit/`, `guide/`, `workflows/` — plan, audit record, human layer, orchestration.

## Evidence status — read before trusting any confidence claim
This workspace was generated in **degraded mode**: no access logs, no APM, and no production
database access were available (contractor handover, no git history, DB access "maybe in a few
weeks" per the task owner). `rebuild.json.evidence` records all three runtime-evidence
subsystems as `inactive`. Concretely:
- Backlog ordering uses problem-brief severity + code-derived risk only, not real usage weight.
- The data census (`docs/migration/census.md`) is schema-derived and provisional, never run
  against real data.
- The replay harness has no T1 (captured production traffic) traces — only T2 (scripted/
  generated) and T3 (statically derived, provisional) tiers. T3 evidence counts toward L2 only,
  never L3.
- Only two defects are attested by human testimony (PB-001 sync email, PB-002 MD5 reset
  tokens — see `docs/problem-brief.md`). Everything else observed in the code that looks like a
  bug or oddity is filed to `docs/open-questions.md` as an ASK or PB proposal, **not** silently
  fixed — see Design Principle 9 in the generating skill: sanctioned change only.

When DB/log access lands, re-run this workspace in **spec-patch mode** (rebuild-kit skill,
resume path) rather than regenerating from scratch: re-run P2/P6/P7 with real evidence, and
re-audit any WO whose risk score was computed without it.

## The executor loop
1. Read `ledger.json`; select the highest-priority WO whose `depends_on` are done and which is
   not blocked by a gate or an open ASK.
2. Load ONLY that WO plus its linked contracts (it declares its context budget).
3. Implement in `modern/` per fidelity tags: exact on FIXED, target behavior on REPAIR,
   idiomatic per modern CLAUDE.md on FREE. Enter `legacy/` only at the WO's escalation
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
no workflow crosses them. Serial execution is always valid, and given this app's small size
(5 legacy files, ~200 lines) serial execution is expected to be sufficient for every milestone.

## Escalation, in one line
Uncertain → open-questions.md; never guess, never improvise on load-bearing behavior, never
touch `legacy/`.
