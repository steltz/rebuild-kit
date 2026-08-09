# 01 — Legacy behavior inventory

Source of truth: `../../ticketd/app/server.py` (plus `util.py`, `notify.py`,
`db/schema.sql`), read 2026-08-08. Every observable behavior is listed and tagged:

- **PRESERVE** — the new service must match this exactly (contract test exists/required).
- **CHANGE** — intentionally different in the rewrite; the difference is specified.
- **DROP** — not ported.
- **DECIDE** — blocked on a question in `decisions/open-questions.md`.

## Code inventory

| File | What it is | Disposition |
|---|---|---|
| `app/server.py` | All 6 routes + dead CSV export | Port per table below |
| `app/util.py` | `slugify()` — lowercase, non-alnum → `-`, strip `-`, truncate 64 | PRESERVE algorithm; collision handling is **DECIDE (Q1)** |
| `app/notify.py` | Blocking SMTP (`smtp.internal:25`, 30 s timeout, sender `ticketd@example.internal`) | CHANGE — outbox + worker, same SMTP host/sender (`specs/04-notifications.md`) |
| `app/legacy_import.py` | 2019 one-off importer, unreferenced | DROP |
| `db/schema.sql` | SQLite DDL: `tickets`, `users`, `reset_tokens` | CHANGE — see `specs/03-data-model.md` |
| `ops/access.log` | Traffic sample | Input to `analysis/access-log-findings.md` |

Git history is 4 commits; 3 are "hotfix N: reset flow" — the reset flow is historically the
fragile part. Treat it with extra test coverage.

## Behavior catalog

### GET /api/tickets

| # | Behavior | Tag |
|---|---|---|
| 1.1 | Returns **all** tickets, no pagination, ordered `created_at DESC`. UI depends on getting everything. | PRESERVE |
| 1.2 | Optional `?status=` filter (exact match). Zero uses in the 30-day log, but it is part of the surface and cheap. | PRESERVE |
| 1.3 | Response: JSON array of full row objects — keys `id, title, slug, priority, status, assignee_id, created_at, closed_at` (nulls included). | PRESERVE |
| 1.4 | Unknown `?status=` values return `[]` (no validation, no error). | PRESERVE |

### POST /api/tickets

| # | Behavior | Tag |
|---|---|---|
| 2.1 | Body JSON; missing/blank `title` (after `.strip()`) → **422** `{"error": "title_required"}`. | PRESERVE |
| 2.2 | Non-JSON or empty body treated as `{}` (→ 422 title_required), never a 400 parse error. | PRESERVE |
| 2.3 | `priority` accepted as string **or** number; `"1"/"2"/"3"` (and numeric `1/2/3`, via `str()`) map to `low/med/high`; absent → `"med"`. Both client styles are live — both must keep working. | PRESERVE |
| 2.4 | Any other priority value is stored as-is by the app, but SQLite CHECK (`low/med/high`) rejects it → legacy responds **500**. New service: validate and return 422. | CHANGE (see Q6 — legacy 500s on bad priority; a clean 422 is a client-visible improvement we take deliberately) |
| 2.5 | `status` starts `'open'`; `created_at` is naive **local-time** ISO string. | CHANGE — store UTC; serialize compatibly (see Q5) |
| 2.6 | Response **201** `{"id": <int>, "slug": "<slug>"}`. | PRESERVE |
| 2.7 | Slug = `slugify(title)`; collisions silently allowed (no unique constraint). | DECIDE (Q1) |
| 2.8 | Only `title` and `priority` are read from the body; `assignee_id`, `status`, etc. in the request are ignored. | PRESERVE |

### GET /api/tickets/{id}

| # | Behavior | Tag |
|---|---|---|
| 3.1 | Found → full row object (same keys as 1.3). | PRESERVE |
| 3.2 | **Missing id → 200 with `{}`, NOT 404.** Historical quirk; legacy UI depends on it. | PRESERVE (do not "fix") |
| 3.3 | Non-integer id → 404 (Flask route converter). FastAPI default is 422 — must be overridden or accepted; log shows only integer ids. | PRESERVE (match 404; trivial via route regex or exception handler) |

### POST /api/tickets/{id}/close

| # | Behavior | Tag |
|---|---|---|
| 4.1 | Sets `status='closed'`, `closed_at=now` only if not already closed. | PRESERVE |
| 4.2 | Response 200 `{"closed": true}` on transition, `{"closed": false}` if already closed **or id does not exist** (no 404). | PRESERVE |
| 4.3 | On transition, emails `watchers@example.internal` body `closed: <title>` — synchronously, in-request. | CHANGE — enqueue in same DB transaction as the close; worker delivers (`specs/04-notifications.md`). Same recipient, same body text. |
| 4.4 | No email when `closed` is false (idempotent replays don't re-notify). | PRESERVE |
| 4.5 | Legacy: if SMTP fails, the request 500s **after** the DB commit (ticket closed, no email, client sees error). New: close never fails due to SMTP; delivery is at-least-once via outbox retry. | CHANGE (this is the June-outage fix) |

### POST /api/auth/reset

| # | Behavior | Tag |
|---|---|---|
| 5.1 | Body `{"email": ...}`; missing email treated as `""` (no validation, still 200). | PRESERVE (yes, it "succeeds" for unknown/empty emails — non-disclosure of account existence) |
| 5.2 | Rate limit: max 3 requests/rolling hour **per email** → 429 `{"error": "rate_limited"}`. | PRESERVE |
| 5.3 | Undocumented header `X-Internal-Bypass: 1` skips the rate limit. | DECIDE (Q2) — headers aren't in the access log, so usage is unknown |
| 5.4 | Token = `md5(email + time)`, stored **plaintext**, emailed as `reset token: <hex>`. | CHANGE — `specs/05-security-reset.md` (token format in the email body changes; the email sentence shape stays `reset token: <token>`) |
| 5.5 | Response 200 `{"ok": true}`; email sent synchronously. | PRESERVE response / CHANGE delivery (outbox) |

### POST /api/auth/reset/confirm

| # | Behavior | Tag |
|---|---|---|
| 6.1 | Body `{"token": ...}`. Invalid **and** expired tokens both → **403** `{"error": "invalid_token"}` with identical body (deliberate non-disclosure). | PRESERVE |
| 6.2 | Expiry window: 30 minutes from creation. | PRESERVE (make it config, default 30) |
| 6.3 | Valid token is deleted → single-use. | PRESERVE (delete/mark-used atomically; legacy has a check-then-delete race — fix silently, not client-visible) |
| 6.4 | Success: 200 `{"ok": true, "email": "<email>"}` — the caller (presumably upstream auth/SSO) consumes the email. | PRESERVE (see Q4 — we don't know who calls this; the log shows 20 calls/period, so it IS live) |

### GET /internal/export/csv

| # | Behavior | Tag |
|---|---|---|
| 7.1 | Dumps id,title,status as (unescaped) CSV. 0 hits in the access log; comment says no caller since the 2020 audit. | DROP, pending Q3 |

### Cross-cutting

| # | Behavior | Tag |
|---|---|---|
| 8.1 | No auth on any endpoint; upstream (gateway) identifies the user. | PRESERVE (Q4 flags it; do not add auth in this rewrite) |
| 8.2 | Timestamps are naive local-time ISO strings (`datetime.now().isoformat()`, microseconds included). | CHANGE — UTC internally; serialization compat per Q5 |
| 8.3 | Errors: legacy returns Flask HTML 500 pages on unhandled errors (~2.5% of logged requests were 500s). New service should return JSON errors; 500 body shape was never part of the UI contract. | CHANGE |
| 8.4 | Runs single-process on port 5000. | CHANGE — uvicorn, port/config per deploy env (Q7) |
