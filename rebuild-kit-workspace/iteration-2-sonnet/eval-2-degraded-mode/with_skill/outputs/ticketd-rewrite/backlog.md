# Backlog — ticketd rewrite

<!-- P8. Ordering: usage weight + pain weight first (both are STATIC PROXIES this run —
     rebuild.json.evidence.runtime_ingestion is inactive, no real traffic exists to weigh
     against), subject to dependency topology. Re-run P8's ordering step via spec-patch once
     real usage data lands; today's order is a reasonable guess, not a measured one. -->

## M0 — Walking skeleton (gate: true, milestone close requires sign-off)

| WO | Title | Depends on | Risk | Gate |
|---|---|---|---|---|
| WO-001 | Walking skeleton: FastAPI+Postgres boots, POST/GET /api/tickets subset | — | 0.35 | true |

Validates the FastAPI + PostgreSQL stack choice and the twin-boot harness plumbing against real
`modern/` code for the first time. Nothing else starts until this closes and a human signs off.

## M1 — Feature parity + both motivating defects repaired

| WO | Title | Depends on | Risk | Gate |
|---|---|---|---|---|
| WO-002 | Tickets: full behaviors (list, create, get) | WO-001 | 0.45 | false |
| WO-004 | Tickets: close (PB-001 primary REPAIR site) | WO-002 | 0.62 | true |
| WO-003 | Auth: password reset (PB-002 REPAIR, PB-001 second site) | WO-001 | 0.68 | true |

This milestone deliberately front-loads BOTH problem-brief defects (PB-001 synchronous email,
PB-002 MD5 tokens) alongside core CRUD parity — "effort follows usage and pain" per the skill's
ordering rule, and the pain here is the entire reason this rewrite was commissioned. WO-003 and
WO-004 are both gated: each rests on an expected-divergence entry that is currently UNSIGNED
(`verification/replay/expected-divergences.yaml`) — a human must rule on ED-001, ED-001b, ED-002
before either WO's L3 result means anything. Milestone close: full-suite regression replay
(`tickets` + `auth-reset` scripts) + human review of the (by-then-signed) divergence manifest.

## M2 — Remaining surface + migration

| WO | Title | Depends on | Risk | Gate |
|---|---|---|---|---|
| WO-005 | Admin: CSV export | WO-002 | 0.25 | false |
| WO-006 | Data migration (tickets, users, reset_tokens) | WO-002, WO-003 | 0.80 | true |

WO-006 is BLOCKED, not just gated — see the WO file. It cannot meaningfully start until
production DB access exists and three open questions (OQ-001, OQ-003, OQ-005) are ruled. It's
listed here so the dependency and the blocker are visible in the plan, not buried.

## Explicitly not on this backlog

- `app/legacy_import.py` — do-not-port (`docs/do-not-port.md#DNP-001`), zero references,
  zero routes.
- Anything not named in the handover notes or found by static reading of this small codebase —
  there is no hidden scope; `docs/problem-brief.md`'s "Open intake questions" section lists what
  wasn't known at generation time (NFRs, non-goals, scale targets).

## What "done" looks like for this rewrite

Per `docs/problem-brief.md`: PB-001 and PB-002 both REPAIRed and passing their (signed)
divergence checks, full CRUD/auth/export behavioral parity with legacy per the FIXED-tagged
behaviors, and the migration WO's reconciliation checks green once data access exists. There is
no NFR target beyond "don't regress the two known defects" — no scale/SLO goal was given.
