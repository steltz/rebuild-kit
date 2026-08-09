# Backlog — ticketd rewrite

Ordering: usage weight + pain weight, topologically constrained. Machine state lives in
`ledger.json`; this file is the human-readable plan. Every milestone closes with a
full-suite regression replay (`diff-run.sh t2-core`), human review of any new
expected-divergence entries, and a guide refresh (`python3 workflows/rk/render_guide.py`).

## M0 — Walking skeleton  *(gate)*
| WO | Title | Risk | Gate |
|---|---|---|---|
| WO-001 | Walking skeleton: list tickets end-to-end (highest-usage flow, 62% of traffic) | 0.45 | yes |

Proves: stack choice (PB-004), twin-boot plumbing (`modern/harness-*.sh`), spec readability.
The M0 sign-off also signs `expected-divergences.yaml` (currently PENDING-HUMAN-SIGNATURE).

## M1 — Tickets core  *(gate at close)*
| WO | Title | Risk | Gate |
|---|---|---|---|
| WO-002 | Create ticket (slug: legacy-exact until OQ-001 rules) | 0.55 | yes |
| WO-003 | Get ticket (the 200-`{}` quirk) | 0.15 | no |
| WO-004 | Close ticket + decoupled notification — **PB-001 repair**, ED-001 | 0.68 | yes |

M1 delivers the outage fix (NFR-1: closing tickets works with SMTP down).
Rulings best landed during M1: OQ-001 (slug), OQ-007 (invalid priority), OQ-004 (mechanism).

## M2 — Auth reset  *(gate at close)*
| WO | Title | Risk | Gate |
|---|---|---|---|
| WO-005 | Reset request — **PB-002 repair** (token storage), ED-002/ED-003 | 0.72 | yes |
| WO-006 | Reset confirm (non-disclosure 403, single-use) | 0.45 | no |

Rulings surfaced at M2: OQ-002 (bypass header), OQ-006 (who consumes confirm's email).

## M3 — Migration & cutover  *(gate)*
| WO | Title | Risk | Gate |
|---|---|---|---|
| WO-007 | Data migration SQLite→Postgres — **blocked by OQ-005** (timezone policy) + census access | 0.75 | yes |
| WO-008 | Rehearsal & cutover (human-owned, cutover.md) | 0.60 | yes |

## Not scheduled (do-not-port)
`GET /internal/export/csv` (DNP-001, ruling OQ-003 open), `app/legacy_import.py` (DNP-002),
expired-token accumulation (DNP-003), dead code fragments (DNP-004).

## Standing prerequisites for the humans
1. Sign `verification/replay/expected-divergences.yaml` (at/before the M0 gate).
2. Rule OQ-001..OQ-007 as they come due (ruling briefs in `guide/briefs/`).
3. Grant read-only prod DB access + PII-scrub approval for the census (blocks WO-007's
   rehearsal; queries are ready in `docs/migration/census-queries.sql`).
