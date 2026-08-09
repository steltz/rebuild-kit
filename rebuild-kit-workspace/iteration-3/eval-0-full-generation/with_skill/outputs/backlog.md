# Backlog — ticketd rewrite

Six work orders across four milestones. Small target (6 legacy routes, 3 tables, 165 LOC) — this
entire backlog is sized to run mostly serially; see root `CLAUDE.md`'s parallel-execution note if
you want to fan out the M1/M2 frontier once M0 is green.

Ordered by usage weight + pain weight within each milestone, subject to dependency order
(`references/schema.md#risk-score`). Usage weights from `usage-weights.json` (P2, same-day
sample — see that file's evidence-quality caveat before treating the exact percentages as
precise). Pain weights are qualitative (problem-brief severity × how directly the WO addresses it).

## M0 — Walking skeleton (gate: true, always — see P8 design rule)

| WO | title | usage wt | pain wt | risk | gate | depends_on |
|---|---|---|---|---|---|---|
| WO-000 | Bootstrap FastAPI + Postgres + Alembic + `GET /api/tickets` (list) end-to-end | 0.6175 | n/a | 0.35 | **true** | — |

Proves the stack choice, the twin-boot harness, and contract fidelity on the single highest-traffic
route before anything else builds on unverified plumbing. No auth layer exists in legacy to slice
through (OQ-007), so "one core action" = the highest-usage read.

## M1 — Tickets subsystem complete

| WO | title | usage wt | pain wt | risk | gate | depends_on |
|---|---|---|---|---|---|---|
| WO-001 | Notification dispatch decoupling (PB-001, cross-cutting infra) | 0.069 | 0.9 | 0.55 | **true** | WO-000 |
| WO-002 | Remaining Tickets endpoints: create, get, close | 0.303 | 0.3 | 0.45 | false | WO-000, WO-001 |

WO-001 ships first within M1 because WO-002's close endpoint depends on it. This is also the
single reason the rewrite was commissioned (June 2026 SMTP outage) — highest pain weight in the
whole backlog. Milestone close requires: full regression replay of `tickets-crud` +
`tickets-close` trace files, human review of ED-001/ED-001b's sign-off (currently UNSIGNED, see
`verification/replay/expected-divergences.yaml`).

## M2 — Auth/Reset subsystem complete

| WO | title | usage wt | pain wt | risk | gate | depends_on |
|---|---|---|---|---|---|---|
| WO-003 | Reset token security mechanism (PB-002, security-flagged) | 0.0195 | 0.9 | 0.65 | **true** | WO-000 |
| WO-004 | Auth/Reset endpoints: request, confirm | 0.0295 | 0.6 | 0.5 | **true** | WO-000, WO-001, WO-003 |

Lowest usage weight in the backlog but among the highest pain weight (security-flagged, PB-002) —
ordered here rather than earlier because it depends on WO-001's notification infra and is
independently gated regardless of traffic share. WO-004 ships with a **known, documented gap**:
the `X-Internal-Bypass` header behavior (PB-008/OQ-002) is neither implemented nor removed — see
WO-004's own file for why guessing either way would be worse than leaving it open. Milestone close
requires ED-002's sign-off (also UNSIGNED) plus a ruling on OQ-002 before WO-004 can move from
`awaiting_ruling` to `done` — the milestone can still close around WO-004 being in that state if
the ruling genuinely isn't available yet, but do not silently mark WO-004 `done` without it.

## M3 — Data migration & cutover (gate: true — data-destructive-adjacent)

| WO | title | usage wt | pain wt | risk | gate | depends_on |
|---|---|---|---|---|---|---|
| WO-005 | Data migration (tickets, users, reset_tokens policy) + cutover checklist | n/a | n/a | 0.7 | **true** | WO-002, WO-004 |

Highest risk score in the backlog. Blocked on **three** open questions (OQ-006, OQ-009, OQ-010)
and on a real data census that could not be run during generation (no production data was
supplied — see `docs/migration/census.md`'s degraded-mode note). Do not schedule this WO's actual
execution until those are addressed; it is placed last in the backlog for exactly that reason, not
because it's less important.

## Problem-brief coverage (P8 step 7 check)

All 10 PB entries hold a disposition as of this generation run (`docs/problem-brief.md`) — none
are `UNDISPOSITIONED`:

| PB | disposition |
|---|---|
| PB-001 (sync SMTP) | REPAIR in WO-001 |
| PB-002 (MD5 tokens) | REPAIR in WO-003 |
| PB-003 (slug collisions) | FIXED for this rewrite (WO-002); OQ-001 open for future enhancement |
| PB-004 (elevated 5xx) | NFR target, now with a traced root cause (P7) |
| PB-005 (stack choice) | ratified, out of scope for debate |
| PB-006 (no UI changes) | ratified non-goal, drives multiple FIXED dispositions |
| PB-007 (200/{} on missing) | FIXED in WO-002 |
| PB-008 (bypass header) | out-of-scope for this rewrite pass (deferred), documented gap in WO-004 |
| PB-009 (dead code) | do-not-port |
| PB-010 (naive timestamps) | FIXED for this rewrite (WO-000/WO-002); OQ-006 open for future REPAIR |

## Open questions that gate real work (not exhaustive — see `docs/open-questions.md` for all 10)

- **OQ-002** blocks WO-004's full close (one code path only).
- **OQ-006, OQ-009, OQ-010** block WO-005's full close.
- Everything else (OQ-001, OQ-003, OQ-004, OQ-005, OQ-007, OQ-008-resolved) is non-blocking for
  the backlog as scoped, per each entry's `blocks:` field.

## What this backlog does NOT include

- No WO for `GET /internal/export/csv` or `legacy_import.py` — both are `do-not-port`
  (`docs/do-not-port.md`), not migrated forward at all, pending OQ-003's pre-cutover confirmation.
- No dedicated "add authentication" WO — legacy has none (OQ-007), and M0 proceeds unauthenticated
  to match it. If OQ-007 is later ruled to require auth, that's new, separately-scoped work not
  currently in this backlog.
