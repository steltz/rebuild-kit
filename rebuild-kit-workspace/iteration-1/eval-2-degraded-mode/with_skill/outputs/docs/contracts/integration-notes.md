# Integration Notes — outbound dependencies & contract looseness

## Outbound: SMTP (the only external integration)
- Legacy: `smtp.internal:25`, blocking, 30s timeout, envelope sender
  `ticketd@example.internal`, raw headerless body (ticketd/app/notify.py:5-7).
- No retry, no queue, no failure handling: an SMTP exception becomes a 500 AFTER the DB
  commit (both call sites — ticketd/app/server.py:72-76 and :93-94), leaving the state
  change applied.
- Modern: dispatch decoupled from requests (PB-001 → ED-001/ED-002); transport env-configured;
  messages well-formed MIME (DNP-003). Harness captures sends on both sides via SMTP stub and
  normalizes them to `schemas/email-dispatch.schema.json` events.

## Contract looseness clients may depend on (Hyrum's law register)
1. Extra JSON body fields are silently ignored on every POST (`get_json` + `.get`) — modern
   models must not reject unknown fields (pydantic: `extra="ignore"`).
2. Non-JSON / missing bodies are treated as `{}` (silent=True) on all three POST-with-body
   routes — modern must not 400 on absent content-type; it falls through to the semantic
   error (422 title_required / rate-limit path with email="").
3. `priority` numeric aliases: integers or strings 1/2/3 (via `str()` coercion). Frozen.
4. `?status=` filter accepts any string, returning [] for unknown values. Frozen.
5. Missing ticket → 200 `{}` — explicitly load-bearing for the legacy UI. Frozen.
6. No-op close (already closed / unknown id) → 200 `{"closed": false}` — no 404. Frozen.
7. Reset request for unknown/empty email → 200 `{"ok": true}` + a real token row + a real
   send attempt to that address. Frozen behavior (see OQ-002 for purpose).
8. Rate-limit bypass header `X-Internal-Bypass: 1` — parity behind default-ON config flag
   until OQ-004 is ruled.

## Sanctioned deviations from observed contract (FREE, recorded)
- Garbage inputs that 500 in legacy return 422 in modern: non-string title
  (AttributeError, ticketd/app/server.py:43), out-of-vocabulary priority incl. float 2.0
  (CHECK IntegrityError, ticketd/app/server.py:50-53 + ticketd/db/schema.sql:5), valid-JSON
  non-object bodies on all three JSON POSTs and non-string reset email (audit A-04/A-13;
  crash sites ticketd/app/server.py:43,83,91-94,100-102). Modern 422 bodies for the two
  replay-exercised probes are pinned by ED-004a/b; the unprobed paths use
  {"error":"request_invalid"} by convention (openapi.yaml components). Rationale in
  docs/features/draft/tickets.md. Replay-exercised probes are covered by expected
  divergences ED-004a-status/-body and ED-004b-status/-body; the authoritative home of
  every ED definition is verification/replay/expected-divergences.yaml.
- Error bodies for framework-level 404 (non-integer path id) are framework-default on both
  sides: status code compared, body not.

## Sandbox availability
Everything twin-boots locally: legacy needs Python + Flask 1.x-compatible runtime + an SMTP
stub; SQLite file is created from ddl.sql. No third-party sandbox needed.
