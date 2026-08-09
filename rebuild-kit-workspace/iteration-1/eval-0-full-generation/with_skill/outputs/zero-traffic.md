# Zero-Traffic Report

Observed window: 30 days · 2000 matched requests (source: `ticketd/ops/access.log`)

Routes in code with no observed traffic. Zero-traffic ≠ dead: check window coverage
(cron/seasonal), admin paths, webhook receivers. Promote to do-not-port.md only with
corroborating static evidence.

- `GET /internal/export/csv` — confidence: **high**. Corroboration: source comment
  "written for the 2020 audit; no caller since" (`ticketd/app/server.py:112`) plus zero
  hits in the 30-day window. Caveat: it was written for an *annual* audit, so a 30-day
  window cannot rule out yearly use — dropping it therefore still needs a human ruling.
  Routed to `docs/do-not-port.md` (DNP-001), ratification tracked as OQ-003.
