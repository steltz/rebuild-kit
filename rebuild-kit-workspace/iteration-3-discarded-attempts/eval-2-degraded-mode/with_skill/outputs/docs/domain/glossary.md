# Glossary

Terms as the code uses them (`ticketd-nohistory/app/server.py`, `db/schema.sql`), not as any
external product doc might use them (none was handed over).

| Term | Meaning in this codebase | Notes |
|---|---|---|
| **ticket** | A row in `tickets`: title, slug, priority, status, timestamps, inert assignee FK. | The sole domain object with a real lifecycle. |
| **slug** | `slugify(title)` — lowercased, non-alphanumeric runs collapsed to `-`, trimmed, capped at 64 chars. | Not guaranteed unique; see `docs/domain/ticket.md` invariants. Returned on ticket creation but not stored as a lookup key by any route (no `GET /api/tickets/by-slug/<slug>` exists). |
| **priority** | One of `low`/`med`/`high`, or the client-facing numeric aliases `1`/`2`/`3`. | Both forms "must keep working" per an explicit code comment (`server.py:46`) — this is existing-client-contract evidence, treat as `FIXED`. |
| **status** | `open` or `closed`. No other values reachable via the API. | DB CHECK allows only these two; app never writes a third. |
| **reset token** | A bearer credential emailed to a user to authorize a password reset (though nothing in this app appears to actually change a password — no `password` field exists anywhere in the schema; see below). | See `docs/domain/reset_token.md`. |
| **rate limit** | 3 reset requests per email per rolling hour, bypassable via `X-Internal-Bypass: 1`. | OQ-002. |
| **watcher(s)** | The fixed recipient `watchers@example.internal` of the ticket-close notification (`server.py:76`). | Not a modeled entity — a hardcoded address, singular in practice despite the plural name. Whether this should become configurable is a FREE choice for the rewrite, not a behavior change. |
| **internal export** | The `/internal/export/csv` route — "internal" here means "written for the 2020 audit," not that it enforces any access restriction (no auth exists on it or any other route). | See DNP-002, OQ-001. |

## Vocabulary gap worth flagging

The system is called a "ticket tracker" and has a full password-**reset** flow, but there is no
`password` field anywhere in the schema and no login/authentication route at all. The reset flow
issues a token and, on confirm, returns `{"ok": true, "email": row["email"]}` — it never touches
a password value, sets a session, or issues any further credential. Either password storage/auth
lives entirely outside this repo (most likely, given zero auth on any endpoint — see OQ-001), or
the reset flow itself is incomplete/vestigial. This isn't a new PB entry (no user testimony named
it), but it materially affects WO-004's scope — see `docs/features/WO-004-password-reset.md`.
