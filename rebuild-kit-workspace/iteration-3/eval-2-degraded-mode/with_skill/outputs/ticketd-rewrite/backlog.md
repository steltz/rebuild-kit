# Backlog

Ordering rule (P8): usage weight + pain weight first, subject to dependency order. This
workspace has no usage weight (degraded — `rebuild.json.evidence.runtime_ingestion: inactive`;
see `usage-weights.json`), so ordering here falls back to pain weight (problem-brief severity)
and dependency/milestone structure only. Every WO below cites the fidelity tags and evidence in
its own file under `docs/features/WO-*.md` — this file is the ordering and milestone view, not
a duplicate of the behavior detail.

## M0 — Walking skeleton (gate: true at milestone close, per executor loop step 8)

Proves the FastAPI+Postgres stack choice and the twin-boot harness plumbing on the smallest
real slice before any REPAIR-bearing work begins.

- **WO-001** — Tickets core (list/create/get). No dependencies. `gate: false` on the WO itself;
  the milestone close still requires human review before M1 starts.

## M1 — Fix what the rewrite was commissioned to fix (PB-001, PB-002)

Both problem-brief defects live here, deliberately ahead of anything else pain-weighted at 0 —
"effort follows usage and pain," and pain is all this workspace has evidence for.

- **WO-004** — Notification dispatch infrastructure (PB-001). No dependencies (foundational for
  this milestone). `gate: true` — see the WO file for the three reasons.
- **WO-002** — Ticket close + notify (PB-001 applied). Depends on WO-001, WO-004.
- **WO-003** — Auth/Reset request + confirm (PB-002 + PB-001 applied). Depends on WO-004.
  `blocked_by_asks: [OQ-001]` — cannot close until that ASK is ruled.

M1 close requires: full-suite regression replay across M0+M1's combined replay sets, human
review of the (currently unratified) `expected-divergences.yaml` entries ED-001/002/003, and a
ruling on OQ-001.

## M2 — Data migration

- **WO-005** — SQLite → Postgres migration. Depends on WO-001, WO-002, WO-003 (schemas must be
  final). `gate: true` — blocked on production DB access
  (`docs/problem-brief.md#OQ-INTAKE-01`) and on `docs/migration/census-queries.sql` actually
  being run; do not start implementation before both are true.

## Unscheduled — pending ASK rulings, not assigned to a milestone

- **WO-006** — CSV export (`/internal/export/csv`). `blocked_by_asks: [OQ-003]`. If OQ-003 is
  ruled "dead code," this WO is deleted and `docs/do-not-port.md#DNP-002` becomes final instead
  of implementing anything.
- `legacy/app/legacy_import.py` — no WO. Candidate do-not-port
  (`docs/do-not-port.md#DNP-001`), pending the same OQ-003 ruling; not a route, nothing to
  schedule either way.
- `users` table / `tickets.assignee_id` — no dedicated WO. Carried forward structurally inside
  WO-001 (schema shape only, FREE) and WO-005 (migration, schema shape only); no behavior exists
  to characterize per `docs/open-questions.md#OQ-004`.

## Problem-coverage check (P8 step 7)

| PB entry | Disposition |
|---|---|
| PB-001 (sync email) | REPAIR in WO-004 (dispatch mechanism) + WO-002/WO-003 (call sites) |
| PB-002 (MD5 tokens) | REPAIR in WO-003 |

Both problem-brief entries are dispositioned. No UNDISPOSITIONED entries remain going into P9.

## Milestone gate summary

| Milestone | Gate | Blocked on |
|---|---|---|
| M0 | true (at close) | Human review of stack/harness proof before M1 starts |
| M1 | true (WO-004 gate, milestone close) | OQ-001 ruling, ED-001/002/003 ratification |
| M2 | true (WO-005 gate) | Production DB access (OQ-INTAKE-01), census run |
| Unscheduled | n/a | OQ-003 ruling (WO-006 existence itself is conditional) |
