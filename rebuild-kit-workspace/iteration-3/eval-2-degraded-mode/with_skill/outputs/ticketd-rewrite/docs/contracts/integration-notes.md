# Integration Notes

## Outbound: SMTP (email notifications)

- **Target**: `smtp.internal:25`, plaintext SMTP (no TLS/STARTTLS observed), connect timeout 30s
  (`legacy/app/notify.py:1-7`).
- **From address**: hardcoded `ticketd@example.internal` (legacy/app/notify.py:7).
- **Call sites**: `close_ticket` (legacy/app/server.py:76) and `request_reset`
  (legacy/app/server.py:94) — both synchronous, in-request (**PB-001**).
- **No retry logic** — a single `smtplib.SMTP(...).sendmail(...)` call; any exception
  (connection refused, timeout, SMTP error) propagates uncaught up through the Flask route,
  which (absent an error handler in this tree) becomes an unhandled-exception 500.
- **No sandbox/test double** exists in the legacy tree — nothing mocks or fakes SMTP for local
  dev or tests found in this codebase (no test files exist at all).
- **Rewrite requirement (PB-001/NFR-001)**: this outbound call must move off the request path.
  Delivery-guarantee level (retry-on-failure outbox vs. best-effort background task) is
  unresolved — see `docs/open-questions.md#OQ-002`.

## Inbound: none

No webhooks, no inbound integrations, no cron triggers found anywhere in the legacy tree.

## Auth: none

No authentication or authorization exists on any route in `legacy/app/server.py`. The
`X-Internal-Bypass` header on `/api/auth/reset` is the only access-control-adjacent mechanism in
the codebase, and it is unauthenticated (any caller can set it) — see
`docs/open-questions.md#OQ-001`.

## Database: SQLite (legacy) → PostgreSQL (target, per rebuild.json.target_stack)

- Legacy: single SQLite file at `db/ticketd.sqlite3` (path relative to CWD,
  `legacy/app/server.py:14`), one connection per Flask app-context (`legacy/app/server.py:20-24`,
  the `g` pattern), no connection pool, no migrations tooling observed (schema is a single
  `db/schema.sql` file, not a migrations directory).
- No production database access is available this run — see `rebuild.json.evidence` and
  `docs/problem-brief.md` OQ-INTAKE-01. `docs/migration/` (P6) is schema-derived only, not
  validated against real data.
