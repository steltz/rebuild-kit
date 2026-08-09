# Rewrite Root — ticketd

This directory is a rewrite workspace. You are the **executor**: you implement the rewrite
described by these artifacts. You never modify `ticketd/` and you never deviate from
legacy behavior without a sanction (a PB entry or a human ruling).

## Layout
- `rebuild.json` — layout block; resolve all paths through it.
  legacy_ref: be1032b5d3a2bb5aadcc9616669e735984dc2230
- `ticketd/` — the existing app. READ-ONLY evidence, pinned (gitlink + chmod + pre-commit
  hook). Open only at cited ranges in escalation pointers; never bulk-read.
- `modern/` — the new app (FastAPI + Postgres). Your sole write target for application
  code. Its CLAUDE.md carries the target stack and conventions.
- `docs/` — specs. `features/WO-*.md` are your work orders; `contracts/` is validated
  against, not interpreted; `open-questions.md` is the ASK register; `do-not-port.md` is
  binding; `problem-brief.md` is the sanction whitelist (PB-nnn).
- `verification/` — the harness. `harness/diff-run.sh` is the acceptance oracle
  (see `harness/README.md`; baseline: selftest 34/34, characterization 21/21 vs legacy).
- `ledger.json` — machine state. You read it to pick work and write it to record results.
- `backlog.md`, `audit/`, `guide/`, `workflows/` — plan, audit record, human layer,
  vendored tooling (`workflows/rk/` — replay differ, guide renderer, staleness check).

## The executor loop
1. Read `ledger.json`; select the highest-priority WO whose `depends_on` are done and which
   is not blocked by a gate or an open ASK (`blocked_by_asks`).
2. Load ONLY that WO plus its linked contracts (it declares its context budget).
3. Implement in `modern/` per fidelity tags: exact on FIXED, target behavior on REPAIR,
   idiomatic per modern/CLAUDE.md on FREE (record each FREE choice in the ledger). Enter
   `ticketd/` only at the WO's escalation pointers.
4. Run L1 (fixtures/contract validation) + L2 (`CHAR_TARGET=modern pytest
   verification/characterization`, the WO's tests) locally; run the WO's replay set through
   the twin-boot harness (L3): `verification/harness/diff-run.sh t2-core` — the WO's
   assigned trace IDs must pass, expected divergences included.
5. Green: mark done in the ledger, record FREE choices made, commit.
6. Red: fix the implementation. If the SPEC appears wrong — or you believe an unsanctioned
   legacy behavior should change — never act silently: file it to `docs/open-questions.md`
   (discrepancy or PB proposal), generate its ruling brief into `guide/briefs/` (template
   pattern: existing OQ briefs there), set the WO `awaiting_ruling` if blocked. Continue
   elsewhere.
7. Gate WOs (`gate: true`): STOP. Emit the gate packet to `guide/briefs/` (pattern:
   `guide/briefs/WO-001-gate-packet.md` skeleton), request human sign-off; the ledger
   records approver and timestamp before the WO closes.
8. Milestone close: full-suite regression replay + human review of any new
   expected-divergence entries; refresh the guide (`python3 workflows/rk/render_guide.py`
   then re-add narrative only via specs); then start the next milestone.

## Hard preconditions the humans still owe (check before relying on the affected parts)
- `verification/replay/expected-divergences.yaml` is PENDING-HUMAN-SIGNATURE — it must be
  signed at/before the M0 gate; L3 acceptance of REPAIR behaviors is provisional until then.
- OQ-005 blocks WO-007; census needs prod access (backlog.md "standing prerequisites").

## Parallel execution (optional, scale permitting)
Between control points you may run the unblocked WO frontier as a dynamic workflow across
worktree-isolated subagents; merges land only through a green harness run; conflicts and
cross-WO discoveries file to open-questions.md. Gates and open ASKs are hard boundaries —
no workflow crosses them. Serial execution is always valid (and sensible at this size).

## Escalation, in one line
Uncertain → open-questions.md; never guess, never improvise on load-bearing behavior, never
touch `ticketd/`.
