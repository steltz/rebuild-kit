# Access log analysis — `ticketd/ops/access.log`

Analyzed 2026-08-08. **Caveat:** the brief describes it as a ~30-day log, but every one of
the 2,000 lines is timestamped `12/Jul/2026` (a single day, ~10:00–11:00 UTC). Treat
absolute volumes as a sample, not a month; the *relative* endpoint mix is still the best
usage evidence available.

## Traffic mix (2,000 requests)

| Endpoint | Count | Share | Latency avg / max (s) |
|---|---|---|---|
| GET /api/tickets | 1,235 (+423 with the POSTs sharing the path)* | 62% | 0.029 / 0.126 |
| POST /api/tickets | 423 | 21% | (mixed into above in latency calc) |
| GET /api/tickets/{id} | 184 | 9% | 0.028 / 0.109 |
| POST /api/tickets/{id}/close | 99 | 5% | 0.131 / 0.364 |
| POST /api/auth/reset | 39 | 2% | 0.111 / 0.306 |
| POST /api/auth/reset/confirm | 20 | 1% | 0.145 / 0.305 |
| GET /internal/export/csv | **0** | — | — |

\* latency aggregation grouped GET+POST on `/api/tickets`: n=1,658, avg 0.029 s.

## Status codes

| Code | Count | Notes |
|---|---|---|
| 200 | 1,948 | includes ticket creations (log shows 200, though the app returns 201 — the log format or a proxy may normalize; don't read too much into it) |
| 500 | 51 | 31 GET list / 12 POST create / 3 GET by-id / 5 close — cause unknown, see open question Q10 |
| 429 | 1 | reset rate limit firing in real traffic — the limit is load-bearing |

## Other observations

- **Single client**: every request is `User-Agent: svc-ui/2.1`. No curl, no scripts, no
  second consumer visible. Strengthens the "wire-compatible with svc-ui and nothing else
  matters" scoping.
- **Single authenticated user** in the identity field (`jdoe@corp.example.com` on all 2,000
  lines) — the log is likely synthetic/scrubbed. Another reason not to over-trust it.
- **No query strings at all** — the `?status=` filter on GET /api/tickets was never used in
  this window (kept anyway; it's cheap — inventory 1.2).
- **Reset flow is live**: 39 requests + 20 confirms. It must work day one.
- Close latency (avg 131 ms, max 364 ms) already reflects SMTP cost on the happy path; the
  outbox design removes that dependency entirely.
- Response sizes for GET /api/tickets reach ~8.6 KB — small; confirms no-pagination is
  currently harmless.

## How this fed decisions

- Drop `/internal/export/csv` (0 hits) — Q3.
- Keep `?status=` despite 0 hits (documented surface, trivial).
- Outbox worker sizing: ~140 emails/window → a 2 s polling loop is overkill-proof.
- Parity tests replay the endpoint mix above (see `verification/verification.md`).
