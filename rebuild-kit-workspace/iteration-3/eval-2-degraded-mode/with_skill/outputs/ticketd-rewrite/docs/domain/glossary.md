# Glossary

- **Ticket** — the primary work item. Has a `title`, derived `slug`, `priority`
  (low/med/high), and lifecycle `status` (open/closed). See `docs/domain/ticket.md`.
- **Slug** — a URL-safe derivation of a ticket's title (`app/util.py:slugify`), lowercased,
  non-alphanumeric runs collapsed to `-`, truncated to 64 chars. Not a stable identifier:
  collisions are possible and not deduplicated (legacy/app/util.py:5). Recomputed on demand,
  not treated as a durable key anywhere in the code.
- **Watcher** — the single hardcoded notification recipient (`watchers@example.internal`,
  legacy/app/server.py:76) for ticket-close events. Not a modeled entity — no table, no route
  to manage watcher lists. The code vocabulary implies a per-ticket or per-team watcher concept
  that does not actually exist yet; flagged here in case that's a gap vs. user expectation, but
  not raised as an OQ since it's a plain absence, not a contradiction between two readings.
- **Reset token** — a single-use, time-limited credential for the password-reset flow. See
  `docs/domain/reset_token.md`. Distinct from "session" or "auth token" — there is no
  authenticated-session concept anywhere in this codebase.
- **Rate limit (reset)** — 3 reset requests per email per rolling hour
  (`RATE_LIMIT_PER_HOUR = 3`, legacy/app/server.py:17), bypassable via an undocumented header.
  See `docs/open-questions.md#OQ-001`.
- **Internal bypass** — the `X-Internal-Bypass: 1` request header that skips the reset rate
  limit (legacy/app/server.py:84). No code vocabulary or documentation explains its intended
  caller.
- **Non-disclosure (reset confirm)** — the deliberate choice to return the same error for
  expired vs. invalid reset tokens, so a caller can't distinguish "this token existed and
  expired" from "this token never existed" (legacy/app/server.py:103-105).
