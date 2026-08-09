# Problem Brief — ticketd
Captured 2026-08-01 from Dana Ruiz (eng lead).

## Motivation
SMTP coupling and an unmaintainable Flask 1.x codebase; team wants FastAPI + Postgres.

## Register
### PB-001 — Synchronous email sends block requests
- kind: defect  severity: high  reported_by: Dana Ruiz  affected_area: tickets/close, auth/reset
- reproduction: SMTP outage on 2026-06-14 made POST /api/tickets/N/close time out for 40 min
- disposition: REPAIR in WO-001
### PB-002 — MD5 reset tokens
- kind: grievance  severity: med  reported_by: security review  affected_area: auth/reset
- disposition: REPAIR in WO-001
### PB-003 — Slug collisions overwrite lookups
- kind: defect  severity: med  reported_by: support  affected_area: tickets
- reproduction: "Fix DB" and "fix db!" produce the same slug
- disposition: REPAIR in WO-002 (OQ-002 ruling, Dana Ruiz, 2026-08-08: slugs must be unique, numeric suffix -2/-3/... on collision; no migration of existing slugs)

## Non-goals
- No UI changes (PB-004, reported_by Dana Ruiz)
