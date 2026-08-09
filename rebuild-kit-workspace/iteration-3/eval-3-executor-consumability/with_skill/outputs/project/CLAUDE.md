# Rewrite Root — ticketd

This directory is a rewrite workspace. You are the **executor**: you implement the rewrite
described by these artifacts. You never modify `ticketd/` and you never deviate from legacy
behavior without a sanction (a PB entry or a human ruling).

ticketd is an internal ticket tracker (Flask 1.x era, running since 2019). The rewrite targets
FastAPI + Postgres (PB-004, `rebuild.json.target_stack`), fixes three named problems (PB-001
synchronous email, PB-002 MD5 reset tokens, PB-003 slug collisions), and changes nothing else
observable — no UI changes (PB-005) means the HTTP contract is frozen except where a PB entry
says otherwise.

## Layout
- `rebuild.json` — layout block; resolve all paths through it. legacy_ref:
  `c28abaddb0dacb789d3b977db736b9d51be02871` (legacy is a nested clone pinned at this SHA; the
  read-only guard also rejects re-pinning it via a bare gitlink commit — see `.githooks/pre-commit`).
- `ticketd/` — the existing app. READ-ONLY evidence, pinned. Open only at cited ranges in
  escalation pointers; never bulk-read. It is a full nested git clone (its own `.git/`), not
  plain files — git itself refuses `git add ticketd/<file>` ("in submodule"), and the
  pre-commit hook additionally rejects any attempt to commit a re-pin of the `ticketd` gitlink.
- `modern/` — the new app. Your sole write target for application code. Its `CLAUDE.md` carries
  the target stack (FastAPI + Postgres) and conventions.
- `docs/` — specs. `features/WO-*.md` are your work orders; `contracts/` is validated against,
  not interpreted; `open-questions.md` is the ASK register; `do-not-port.md` is binding.
- `verification/` — the harness. `harness/diff-run.sh` is the acceptance oracle.
- `ledger.json` — machine state. You read it to pick work and write it to record results.
- `backlog.md`, `audit/`, `guide/`, `workflows/` — plan, audit record, human layer, orchestration.

## The executor loop
1. Read `ledger.json`; select the highest-priority WO whose `depends_on` are done and which is
   not blocked by a gate or an open ASK.
2. Load ONLY that WO plus its linked contracts (it declares its context budget).
3. Implement in `modern/` per fidelity tags: exact on FIXED, target behavior on REPAIR,
   idiomatic per `modern/CLAUDE.md` on FREE. Enter `ticketd/` only at the WO's escalation
   pointers.
4. Run L1 + L2 locally; run the WO's replay set through the twin-boot harness (L3), expected
   divergences included (`verification/replay/expected-divergences.yaml`).
5. Green: mark done in `ledger.json`, record FREE choices made, commit.
6. Red: fix the implementation. If the SPEC appears wrong — or you believe an unsanctioned
   legacy behavior should change — never act silently: file it to `docs/open-questions.md`
   (discrepancy or PB proposal), generate its ruling brief into `guide/briefs/`, set the WO
   `awaiting_ruling` if blocked. Continue elsewhere.
7. Gate WOs (`gate: true`): STOP. Emit the gate packet to `guide/briefs/`, request human
   sign-off; the ledger records approver and timestamp before the WO closes.
8. Milestone close: full-suite regression replay + human review of any new expected-divergence
   entries; refresh the guide's as-built pages; then start the next milestone.

## Known blockers a fresh executor session should check first
No human was available to answer questions while this workspace was generated (see
`docs/problem-brief.md#open-intake-questions`). Two open items can block early work orders:
- **OQ-001** (PB-003, blocks WO-005 close): slug-collision resolution mechanism unruled.
- **OQ-002** (PB-related, OIQ-4, flags gate review, blocks nothing outright but affects every
  WO touching auth): does the FastAPI app need to implement authentication itself, or does an
  upstream proxy keep injecting identity as it appears to today? The legacy app has **no** auth
  code at all — every route is open. Building auth nobody asked for would be unsanctioned scope
  creep; building nothing when the proxy assumption is wrong ships an open ticket tracker.
  Get a human ruling before Milestone 0 if at all possible; Milestone 0 is written to be
  answerable either way (see `backlog.md`), but every WO past M0 that touches request
  identity depends on this.

## Parallel execution (optional, scale permitting)
Between control points you may run the unblocked WO frontier as a dynamic workflow across
worktree-isolated subagents; merges land only through a green harness run; conflicts and
cross-WO discoveries file to `open-questions.md`. Gates and open ASKs are hard boundaries — no
workflow crosses them. Given the size of this app (5 source files, 6 routes), serial execution
by a single session is entirely reasonable and is the recommended default; parallelism buys
little here and costs coordination overhead.

## Escalation, in one line
Uncertain → `docs/open-questions.md`; never guess, never improvise on load-bearing behavior,
never touch `ticketd/`.
