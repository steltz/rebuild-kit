# Integration Notes — boundaries, looseness, and outbound dependencies

## Clients

Single observed client: `svc-ui/2.1` (User-Agent on all 2000 log lines,
`ticketd/ops/access.log`). No API keys, no auth headers — perimeter-trusted internal
service. The rewrite keeps the surface anonymous (PB-005: the UI sends no credentials).

## Hyrum's-law looseness the code tolerates (preserve unless a PB sanctions otherwise)

1. **Non-JSON request bodies are tolerated** on every POST (`get_json(silent=True)`,
   `ticketd/app/server.py:42,82,100`) — malformed JSON behaves like `{}`, it never 400s.
2. **Unknown body fields ignored** everywhere (only named keys are read).
3. **Priority as number or string** (`ticketd/app/server.py:46-49`); values outside the
   known set → 500 (OQ-007).
4. **`GET /api/tickets/<id>` returns 200 `{}`** for missing rows — the UI depends on it
   (`ticketd/app/server.py:62-63`).
5. **No pagination** on the list route — the UI fetches everything
   (`ticketd/app/server.py:35`).
6. **`?status=` accepts anything**, unknown values return `[]` not 400.
7. **`X-Internal-Bypass: 1`** skips the reset rate limit (`ticketd/app/server.py:84`,
   OQ-002) — someone may be using this.

## Outbound dependencies

- **SMTP** `smtp.internal:25` — plain, unauthenticated, 30s timeout, no retry
  (`ticketd/app/notify.py:5-7`). Messages are headerless raw bodies from
  `ticketd@example.internal` (NT-2). After PB-001's repair, delivery becomes at-least-once
  from a decoupled dispatcher; SMTP unavailability must not affect any request path (NFR-1).
  No sandbox needed: the harness substitutes a capture sink on both sides.

## Inbound webhooks / events / cron

None (verified — `docs/00-overview.md`).

## Status-code caveat

Prod access log records 200 for POST /api/tickets where the pinned code returns 201
(OQ-009). If a fronting proxy is normalizing statuses, the modern deploy behind the same
proxy will match prod; the L3 harness compares app-level statuses (201).
