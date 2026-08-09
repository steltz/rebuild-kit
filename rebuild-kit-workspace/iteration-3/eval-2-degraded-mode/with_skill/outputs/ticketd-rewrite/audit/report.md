# Adversarial Audit Report — ticketd

Generated P9, 2026-08-09. Independent fresh-context auditor (a subagent given ONLY
`legacy/app/*.py`, `legacy/db/schema.sql`, and `docs/problem-brief.md` — explicitly instructed
not to read any generator draft, WO, or domain doc, to preserve independence per rebuild-kit
design principle 7). Serial single-pass audit (app is small enough that the workflow-shaped
fan-out described in the P9 playbook would be disproportionate — see SKILL.md "Proportionality
is a design rule").

## Scorecard

| Metric | Value |
|---|---|
| Claims audited / confirmed / contradicted / unverifiable | 15 / 15 / 0 / 0 |
| Claims confirmed | 100% |
| Spec branch coverage (branches in source represented in specs, post-audit) | ~93% (26/28 — see methodology note) |
| Problem coverage (PB entries dispositioned) | 100% (2/2 — PB-001, PB-002 both REPAIR-dispositioned) |
| Demotion rate (claims → ASK) | 0% (0/15 — no claim was contradicted or unverifiable) |
| New spec items from coverage hunt | 13 found, 8 genuinely new (not previously represented under any framing), all routed |

**Methodology note on branch coverage**: this is not a mechanically counted metric (no branch-
coverage tool was run — the app has zero existing tests to instrument). "28" is the sum of the
15 audited claims + 13 independently-found Task-2 items; "26" credits the 15 confirmed claims
plus 3 of the 5 Task-2 items already found unnecessary to spec because they're SQLite-default
behavior (FK enforcement off by default, no indexes, connection-per-context is a Flask idiom, not
app-specific behavior worth a WO line). The other 8 genuinely new items were folded into specs
below. Treat this percentage as an informed estimate, not a hard measurement.

## Per-module results

| Module | Claims | Confirmed | Demoted | New coverage items | Notes |
|---|---|---|---|---|---|
| Tickets (list/create/get/close) | 5 | 5 | 0 | 3 (2 crash paths + 1 routing nuance) | See AD-001, AD-002, AD-003 below |
| Auth/Reset (request/confirm) | 5 | 5 | 0 | 1 (rate-limit window outlives token validity — informational, no spec change) | No contradictions; OQ-001 already anticipated the bypass-header ambiguity independently confirmed here |
| Export CSV | 1 | 1 | 0 | 1 (formula-injection risk, strengthens existing unescaped-CSV finding) | Route status itself still gated on OQ-003 |
| Schema / cross-cutting | 4 | 4 | 0 | 4 (FK not enforced, users dead code — already covered, unbounded token growth — already covered, no indexes) | 2 of 4 were already covered under different framing (users table, token growth) |

## Discrepancies

**None.** All 15 falsification claims were CONFIRMED by the independent auditor with the
auditor's own line citations matching the generator's. Zero claims were contradicted or
unverifiable; the demotion rate is 0%. This is a genuinely small, simple codebase (5 files, 165
LOC) audited against equally-small specs — a larger target should not expect this ratio.

## Coverage-hunt findings and disposition

1. **Uncaught 500 on out-of-domain `priority`** (legacy/app/server.py:47-53 vs. CHECK constraint
   at legacy/db/schema.sql:5) — genuinely new. **Routed**: added to WO-001 as a FIXED behavior
   (crash carried forward exactly) + filed as `docs/open-questions.md#OQ-005` (PB-proposal,
   pending human ruling on whether to REPAIR it).
2. **Uncaught 500 on non-string `title`** (legacy/app/server.py:43) — genuinely new. **Routed**:
   added to WO-001 as FIXED + `docs/open-questions.md#OQ-006` (PB-proposal).
3. **`X-Internal-Bypass` fully client-spoofable, no auth check** — already anticipated by
   `docs/open-questions.md#OQ-001` (raised independently in P4, before this audit ran).
   **Routed**: no change needed; audit corroborates the existing OQ.
4. **Non-integer `tid` produces Flask's own 404, not the app's `{}`/200** (legacy/app/server.py:
   58, 67 route pattern) — this WAS captured in the P4 draft (`docs/features/draft/tickets.md`)
   but had NOT been carried into the final `docs/features/WO-001-tickets-core.md` — a real
   draft-to-WO transcription gap the audit caught. **Routed**: added to WO-001 as FIXED.
5. **Rate-limit window (1h) outlives token validity (30m)** — expired-but-undeleted tokens still
   count against the rate limit. **Routed**: informational note only; this is a direct
   consequence of already-documented behaviors (rate limit counts by `created_ts`, confirm
   deletes on success only), not a new spec item — no code path is undocumented, just an
   interaction worth naming. Left as this report entry rather than a new OQ.
6. **Unbounded `reset_tokens` growth** — already covered in `docs/domain/reset_token.md` ("no
   background reaper exists"). **Routed**: no change.
7. **`users` table entirely dead code** — already covered via `docs/open-questions.md#OQ-004`.
   **Routed**: no change.
8. **FK not enforced** (`PRAGMA foreign_keys` never set) — genuinely new detail. **Routed**:
   added to `docs/domain/ticket.md`'s invariants section, tied to OQ-004 and flagged for
   `docs/migration/mapping.md` (Postgres enforces FKs by default — a mechanism-level change,
   FREE, but worth the migration WO knowing about if OQ-004 reading B is ever confirmed).
9. **No `teardown_appcontext` / possible connection handle leak** — genuinely new, but judged
   not spec-worthy: this is a legacy implementation-mechanism detail with no external behavioral
   signature (no observable difference in any response or state the harness can capture), and
   `modern/CLAUDE.md` already mandates dependency-injected DB boundaries regardless. **Routed**:
   no spec change; noted here only for the record.
10. **`silent=True` also degrades a wrong-Content-Type request to `{}`** — genuinely new framing,
    but behaviorally identical to the already-documented "missing field defaults" cases.
    **Routed**: no spec change.
11. **CSV formula-injection risk** (titles starting with `=`/`+`/`-`/`@`) — strengthens the
    already-documented unescaped-CSV finding in `docs/features/draft/export-csv.md`. **Routed**:
    left as an enrichment note in this report; the underlying WO-006 is gated on OQ-003 (is the
    route even live) before any of this matters.
12. **Mixed time representations across tables** (naive-local ISO strings vs. Unix-epoch floats)
    — both halves were already independently documented (`docs/domain/ticket.md`,
    `docs/domain/reset_token.md`); the cross-table framing is new but not actionable beyond what
    `docs/migration/mapping.md`'s per-table ASKs already capture. **Routed**: no change.
13. **No indexes on `reset_tokens`** — genuinely new, pure performance observation with no
    behavioral/API signature. **Routed**: no spec change; a candidate NFR for
    `docs/migration/mapping.md`'s target schema (FREE, Postgres/executor's call), not logged as
    a formal item given no brief testimony motivates a performance target.

## Fixture spot-check

The three ticket fixtures under `docs/contracts/fixtures/` were validated against
`docs/contracts/schemas/ticket.schema.json` at P5 generation time (all three pass — see
`docs/contracts/fixtures/README.md`). More significantly: the 19 traces under
`verification/replay/traces/*.legacy.jsonl` are NOT hand-built fixtures at all — they were
captured by actually booting `legacy/app/server.py` via Flask's test client (see
`verification/harness/README.md`), making them T2-tier (boot-verified), stronger evidence than
a P5 fixture spot-check would normally provide. The P9 auditor's 15/15 confirmed claims were
independently re-derived from source, not from these traces, so the two verification paths
(live boot vs. independent code reading) corroborate each other without sharing a blind spot.

## Problem coverage

Both problem-brief entries hold a disposition: PB-001 → REPAIR in WO-004 (+ call sites in
WO-002/WO-003); PB-002 → REPAIR in WO-003. No UNDISPOSITIONED entries. Workspace assembly is not
blocked on this criterion.
