# Rewrite Root — ticketd

This directory is a rewrite workspace. You are the **executor**: you implement the rewrite
described by these artifacts. You never modify `ticketd-nohistory/` and you never deviate from
legacy behavior without a sanction (a PB entry or a human ruling).

## Layout
- `rebuild.json` — layout block; resolve all paths through it.
  legacy_ref: `tree-02fcc10c238482f7672caacb333b91cb3a84e39d0262868efad28f3e524fc0a3`
  (unversioned-snapshot — no git history was handed over with the legacy app, so the pin is a
  content hash of the tree at scaffold time, not a SHA. `scripts/staleness_check.py` still works
  against it.)
- `ticketd-nohistory/` — the existing Flask/SQLite app. READ-ONLY evidence, pinned. Open only at
  cited ranges in escalation pointers; never bulk-read. Enforced by filesystem permissions (files
  chmod'd read-only) AND a pre-commit hook that rejects any staged diff under this path — both
  were verified working at scaffold time.
- `modern/` — the new FastAPI + PostgreSQL app. Your sole write target for application code. Its
  CLAUDE.md carries the target stack and conventions.
- `docs/` — specs. `features/WO-*.md` are your work orders; `contracts/` is validated against,
  not interpreted; `open-questions.md` is the ASK register; `do-not-port.md` is binding.
- `verification/` — the harness. `harness/diff-run.sh` is the acceptance oracle.
- `ledger.json` — machine state. You read it to pick work and write it to record results.
- `backlog.md`, `audit/`, `guide/`, `workflows/` — plan, audit record, human layer, orchestration.

## Evidence status (read before trusting any usage/priority claim)
This workspace was generated **without** runtime logs, APM, analytics, or production database
access (see `rebuild.json.evidence` and PB-003 in `docs/problem-brief.md`). Concretely:
- Backlog ordering uses a **static proxy** for usage weight (route count x inbound-reference
  count), not observed traffic — treat WO ordering as a reasonable guess, not measured priority.
- There are no perf envelopes (p50/p95/p99) — no NFR latency floors exist to regress against.
- `docs/migration/census.md` ships as queries to run, not results — the data census has not
  happened yet.
- Replay traces are T2 (scripted) and T3 (statically derived, provisional) only — no T1 captured
  production traffic exists. T3 evidence counts toward L2, never L3.
When runtime/DB evidence lands, re-run P2/P6 as a spec-patch (see the skill's
`references/phases/spec-patch.md`) before trusting priority-sensitive decisions.

## The executor loop
1. Read `ledger.json`; select the highest-priority WO whose `depends_on` are done and which is
   not blocked by a gate or an open ASK.
2. Load ONLY that WO plus its linked contracts (it declares its context budget, ~350 lines).
3. Implement in `modern/` per fidelity tags: exact on FIXED, target behavior on REPAIR, idiomatic
   FastAPI/PostgreSQL choice per `modern/CLAUDE.md` on FREE. Enter `ticketd-nohistory/` only at
   the WO's escalation pointers.
4. Run L1 (OpenAPI/schema/DDL validation) + L2 (characterization tests) locally; run the WO's
   replay set through `verification/harness/diff-run.sh` (L3), expected divergences included.
5. Green: mark done in `ledger.json`, record any FREE choices made, commit.
6. Red: fix the implementation. If the SPEC appears wrong — or you believe an unsanctioned legacy
   behavior (e.g. OQ-001, no auth on any endpoint; OQ-002, the `X-Internal-Bypass` header) should
   change — never act silently: file it to `docs/open-questions.md` (discrepancy or PB proposal),
   generate its ruling brief into `guide/briefs/`, set the WO `awaiting_ruling` if blocked.
   Continue elsewhere.
7. Gate WOs (`gate: true`): STOP. Emit the gate packet to `guide/briefs/`, request human sign-off;
   `ledger.json` records approver and timestamp before the WO closes.
8. Milestone close: full-suite regression replay + human review of any new expected-divergence
   entries; refresh the guide's as-built pages; then start the next milestone.

## Parallel execution (optional, scale permitting)
This is a ~150-line, 4-file legacy app — serial execution is expected to be sufficient for the
whole rewrite, and is always valid. If you do parallelize between control points, run the
unblocked WO frontier as a dynamic workflow across worktree-isolated subagents; merges land only
through a green harness run; conflicts and cross-WO discoveries file to open-questions.md. Gates
and open ASKs are hard boundaries — no workflow crosses them.

## Escalation, in one line
Uncertain → open-questions.md; never guess, never improvise on load-bearing behavior, never touch
`ticketd-nohistory/`.
