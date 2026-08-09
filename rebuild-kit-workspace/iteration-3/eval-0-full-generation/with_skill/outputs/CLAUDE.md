# Rewrite Root — ticketd

This directory is a rewrite workspace. You are the **executor**: you implement the rewrite
described by these artifacts. You never modify `ticketd/` and you never deviate from legacy
behavior without a sanction (a PB entry or a human ruling).

ticketd is a small internal ticket tracker (Flask 1.x, SQLite, ~165 LOC across 4 modules, 6
routes, 3 tables) being rewritten to FastAPI + Postgres. The rewrite exists because a synchronous
SMTP call inside `close_ticket()` took ticket-closing down org-wide for ~40 minutes during the
June 2026 SMTP outage (PB-001) — see `docs/problem-brief.md` for the full register. **No UI
changes are in scope**: every HTTP contract behavior the current UI depends on (status codes,
response shapes, the int-or-string `priority` field, the empty-object-on-missing-id quirk) is a
FIXED requirement, not a cleanup target.

This workspace was generated non-interactively (no human was available to answer clarifying
questions during generation) — several problem-brief entries and open questions are marked
UNDISPOSITIONED or PENDING for exactly that reason. Read `docs/open-questions.md` before assuming
any ambiguous legacy behavior has a settled answer; do not resolve OQ entries yourself.

## Layout
- `rebuild.json` — layout block; resolve all paths through it. legacy_ref:
  `1cc113597ea87990e731f02190fc6999e42e7cd8` (the git-ai authorship-metadata commits on top of it
  in `ticketd/.git` are tooling noise, not app history — the pin is the app-code HEAD).
- `ticketd/` — the existing app. READ-ONLY evidence, pinned. Open only at cited ranges in
  escalation pointers; never bulk-read. A pre-commit hook (`.githooks/pre-commit`) rejects any
  diff under this directory.
- `modern/` — the new FastAPI + Postgres app. Your sole write target for application code. Its
  `CLAUDE.md` carries the target stack and conventions.
- `docs/` — specs. `features/WO-*.md` are your work orders; `contracts/` is validated against, not
  interpreted; `open-questions.md` is the ASK register (7 open entries as of generation — read it);
  `do-not-port.md` is binding (2 entries: the CSV export endpoint, the dead importer module).
- `verification/` — the harness. `harness/diff-run.sh` is the acceptance oracle. Evidence caveat:
  this rewrite has **no T1 captured traffic** (only a Combined-Log-Format access log with no
  request/response bodies) and **no real production data** (SQLite file was never supplied) — the
  replay corpus is T2 (scripted twin-boot sessions, generate as you implement each WO) and T3
  (statically derived from source reading, provisional, counts toward L2 only). See
  `docs/problem-brief.md`'s evidence notes and `rebuild.json.evidence` before trusting any claim
  of "verified against production traffic."
- `ledger.json` — machine state. You read it to pick work and write it to record results.
- `backlog.md`, `audit/`, `guide/`, `workflows/` — plan, audit record, human layer, orchestration.

## The executor loop
1. Read `ledger.json`; select the highest-priority WO whose `depends_on` are done and which is
   not blocked by a gate or an open ASK.
2. Load ONLY that WO plus its linked contracts (it declares its context budget).
3. Implement in `modern/` per fidelity tags: exact on FIXED, target behavior on REPAIR, idiomatic
   per `modern/CLAUDE.md` on FREE. Enter `ticketd/` only at the WO's escalation pointers.
4. Run L1 + L2 locally; run the WO's replay set through the twin-boot harness (L3), expected
   divergences included.
5. Green: mark done in the ledger, record FREE choices made, commit.
6. Red: fix the implementation. If the SPEC appears wrong — or you believe an unsanctioned legacy
   behavior should change — never act silently: file it to `docs/open-questions.md` (discrepancy
   or PB proposal), generate its ruling brief into `guide/briefs/`, set the WO `awaiting_ruling` if
   blocked. Continue elsewhere.
7. Gate WOs (`gate: true`): STOP. Emit the gate packet to `guide/briefs/`, request human sign-off;
   the ledger records approver and timestamp before the WO closes. WO-000, WO-001, WO-003, WO-004,
   WO-005 all carry `gate: true` (see `backlog.md`); WO-004 additionally cannot leave
   `awaiting_ruling` for the `X-Internal-Bypass` header path without OQ-002's ruling, and WO-005
   cannot fully close without OQ-006/OQ-009/OQ-010 — do not guess any of these.
8. Milestone close: full-suite regression replay + human review of any new expected-divergence
   entries; refresh the guide's as-built pages; then start the next milestone.

## Parallel execution (optional, scale permitting)
This is a small target (6 endpoints, 3 tables) — serial execution through the backlog is
perfectly reasonable and is the expected mode. If you do parallelize, between control points you
may run the unblocked WO frontier as a dynamic workflow across worktree-isolated subagents; merges
land only through a green harness run; conflicts and cross-WO discoveries file to
`open-questions.md`. Gates and open ASKs are hard boundaries — no workflow crosses them.

## Escalation, in one line
Uncertain → `docs/open-questions.md`; never guess, never improvise on load-bearing behavior, never
touch `ticketd/`.
