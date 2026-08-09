# ticketd rewrite: context and constraints

## Why

Leadership approved a full rewrite of `ticketd` (internal ticket tracker,
Flask 1.x + SQLite, running since 2019) after the June 2026 SMTP outage took
ticket-closing down for 40 minutes — `POST /api/tickets/<id>/close` sends its
notification email synchronously, inside the request, with a 30s SMTP
timeout (`ticketd/app/notify.py`). When SMTP degrades, every close request
degrades with it, and at sustained volume the app's workers saturate.

Two more problems are known and explicitly in scope:

1. **Password-reset tokens are MD5 hashes in a bare table.** Flagged by
   security. `ticketd/app/server.py::request_reset` derives the token as
   `md5(email + time.time())` — weak hash *and* low-entropy, guessable
   input — and stores it in plaintext in a table with no PK, no index, no
   expiry column.
2. **Slug collisions.** `ticketd/app/util.py::slugify` is lossy
   (`"Fix DB"` and `"fix db!"` both become `"fix-db"`) and the schema has no
   uniqueness constraint on `slug`. **Nobody has decided what the fix should
   be yet** — this workspace proposes a default (see
   `DESIGN-slug-collisions.md`) but it needs sign-off; it is not settled the way
   the SMTP and MD5 fixes are.

## Decided

- **New stack: FastAPI + Postgres.** Not up for debate in this workspace —
  leadership picked it for the team's existing expertise. All plans in
  `plans/` assume this stack.
- **Out of scope: any UI changes.** The frontend (`svc-ui/2.1`, per the
  access log) is not being touched. This is the single most important
  constraint on the rewrite: **the new backend's API contract must remain
  compatible with what the existing UI expects**, including quirks that look
  like bugs (see `01-CURRENT-BEHAVIOR-CONTRACT.md` — especially the
  `GET /api/tickets/<id>` 404-vs-200-empty-object behavior, which is
  explicitly UI-load-bearing per a code comment). "No UI changes" is being
  read as "no changes to what the UI receives or must do," not merely "don't
  edit UI source files" — a backend change that silently changes response
  shape/semantics the UI depends on is treated as equivalent to a UI change
  here, and is out of scope unless it's one of the three named fixes below.

## In scope (the three named fixes)

1. **Make ticket-closing resilient to SMTP being slow or down.** Notification
   email must not block the `close` request or be able to take the API down
   with it. See `plans/03-async-notifications.md`.
2. **Replace MD5 reset tokens with a secure scheme**, without changing the
   two response shapes the UI depends on (`POST /api/auth/reset` →
   `{"ok": true}`; `POST /api/auth/reset/confirm` → `{"ok": true, "email":
   ...}` or the non-disclosure `403 {"error": "invalid_token"}`). See
   `plans/04-secure-password-reset.md`.
3. **Stop slug collisions.** Default proposal: uniqueness enforced at the DB
   level with deterministic suffixing on collision (see
   `DESIGN-slug-collisions.md`). **This is a proposal, not a decision** —
   flagged in `03-OPEN-QUESTIONS.md` item 2.

## Explicitly out of scope (do not build these without new sign-off)

- Any UI/frontend work.
- Authentication/authorization — the legacy API has none; the rewrite
  preserves that (see open question about whether an upstream gateway
  handles auth today).
- New features: ticket assignment (the `assignee_id` column exists but is
  unused by any endpoint — do not wire it up as part of this rewrite),
  comments, attachments, search, webhooks, etc. None of that was asked for.
  If it comes up mid-rewrite, that's scope creep — stop and flag it rather
  than building it.
- Porting `app/legacy_import.py` (one-off 2019 spreadsheet importer, unused,
  dead code — leave it behind).
- Deciding whether `GET /internal/export/csv` survives — see open questions.

## Success criteria

- All six live endpoints (`GET/POST /api/tickets`, `GET /api/tickets/<id>`,
  `POST /api/tickets/<id>/close`, `POST /api/auth/reset`, `POST
  /api/auth/reset/confirm`) behave identically to today from the UI's point
  of view, **except** where a behavior change is one of the three named
  fixes above or an explicitly-approved item in `03-OPEN-QUESTIONS.md`.
- `POST /api/tickets/<id>/close` returns to the caller without waiting on
  SMTP, and a full SMTP outage no longer degrades the API's ability to close
  tickets (verified by the load test in `verification/`).
- No plaintext or MD5-derived reset tokens are stored anywhere at rest.
- Two tickets with visually-colliding titles get distinct slugs.
- Legacy SQLite data (`tickets`, `users`) is migrated into Postgres with
  matching IDs. `reset_tokens` is **not** migrated (see
  `plans/06-migration-and-cutover.md` — tokens are short-lived, will have
  expired long before cutover, and can't be represented in the new hashed
  scheme anyway).

## How this workspace is organized

See `README.md` for the full index and execution order. Short version: read
`01`–`04` for context, resolve or accept the defaults in
`03-OPEN-QUESTIONS.md`, then execute `plans/00`...`plans/06` in order, each
via `superpowers:subagent-driven-development` or
`superpowers:executing-plans`, verifying with `verification/` after each
phase that touches behavior.
