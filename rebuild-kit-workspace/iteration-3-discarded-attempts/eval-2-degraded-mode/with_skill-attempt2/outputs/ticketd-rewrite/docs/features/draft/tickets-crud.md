# Draft Feature Spec — Tickets (list / create / get / close / export)

Subsystem: Tickets (`docs/00-overview.md`). All confidence tags are `cited` (file:line) — no
`traced` claims exist anywhere in this workspace (T1/runtime evidence inactive,
`docs/no-runtime-evidence-report.md`). Self-verification pass: every citation below was
re-read against `legacy/app/server.py` a second time after first draft, confirming line numbers
and behavior before this file was finalized (serial fallback for P4's paired extract-and-verify,
per the phase playbook — no second agent was used given app size).

## GET /api/tickets — list

1. Optional `status` query param filters by exact match; omitted = all tickets.
   fidelity: FIXED · evidence: `legacy/app/server.py:29-34`
2. Always ordered `created_at DESC`, regardless of filter.
   fidelity: FIXED · evidence: `legacy/app/server.py:36`
3. **No pagination** — returns the entire result set in one response body. Comment: "the UI
   relies on getting everything and filtering client-side."
   fidelity: FIXED · evidence: `legacy/app/server.py:35` · see OQ-003 (scale unknown; ASK
   whether pagination should be added as a FREE improvement)
4. Response: JSON array of ticket objects (all columns, via `dict(sqlite3.Row)`), `200` always
   (empty array if no matches, never an error for zero results).
   fidelity: FIXED · evidence: `legacy/app/server.py:36-37`

## POST /api/tickets — create

1. Missing/empty (after `.strip()`) `title` → `422 {"error": "title_required"}`.
   fidelity: FIXED · evidence: `legacy/app/server.py:43-45`
2. `priority`: accepts `"1"`/`"2"`/`"3"` (mapped to `low`/`med`/`high`) or a literal
   `low`/`med`/`high` string; anything else is passed through raw. Comment confirms dual-format
   intent: "clients send both, both must keep working."
   fidelity: FIXED · evidence: `legacy/app/server.py:46-49` · see OQ-002 (dual-format still
   required? no client code available to confirm)
3. **Unmapped `priority` values are not rejected in application code** — they hit the sqlite
   `CHECK` constraint and raise an unhandled `sqlite3.IntegrityError` (500, no structured error
   body). This is not self-flagged in a comment and does not match either known PB.
   fidelity: FIXED (preserve; no PB sanctions changing it) · evidence:
   `legacy/app/server.py:47-50`, `legacy/db/schema.sql:5` · **pb-proposal filed: OQ-008** — if
   ruled, target behavior would be a clean `422` instead of an unhandled `500`.
4. Defaults `priority` to `"med"` if omitted from the request body.
   fidelity: FIXED · evidence: `legacy/app/server.py:47`
5. `status` is always set to `'open'` at creation — not client-settable.
   fidelity: FIXED · evidence: `legacy/app/server.py:51`
6. `slug` is derived server-side via `slugify(title)`; not client-settable; not guaranteed
   unique (no DB constraint, collisions possible per `util.py:5` comment).
   fidelity: FIXED · evidence: `legacy/app/server.py:51,55`, `legacy/app/util.py:4-6`
7. `created_at` stored as `datetime.now().isoformat()` — naive local time, no timezone.
   fidelity: FIXED, but flagged as pb-proposal **OQ-005** (naive-datetime — accepted limitation
   or bug?) · evidence: `legacy/app/server.py:52` (self-flagged in source: "naive local time!")
8. Success response: `201 {"id": <int>, "slug": <str>}`. No email/notification side effect on
   create (only close and reset trigger email — see below and Auth/Reset spec).
   fidelity: FIXED · evidence: `legacy/app/server.py:54-55`

## GET /api/tickets/<id> — get

1. Existing ticket: `200` with the full ticket object.
   fidelity: FIXED · evidence: `legacy/app/server.py:64`
2. **Nonexistent ticket: `200` with `{}`, NOT `404`.** Explicit comment: "historical quirk ...
   the legacy UI depends on it." No legacy UI was included in this handover to verify the claim.
   fidelity: FIXED (preserve, per the in-source comment) · evidence: `legacy/app/server.py:61-63`
   · see **OQ-001** — ruling requested since the dependency can't be independently confirmed.

## POST /api/tickets/<id>/close — close

1. Only transitions tickets where `status != 'closed'` (idempotent guard) — closing an
   already-closed ticket is a no-op.
   fidelity: FIXED · evidence: `legacy/app/server.py:69-70`
2. On successful transition: sets `status = 'closed'`, `closed_at = now()` (naive local time,
   same as `created_at` — see OQ-005), commits, THEN **synchronously sends an email** to the
   hardcoded address `watchers@example.internal` inside the same request
   (`smtplib.SMTP(..., timeout=30)`), **before** returning the response.
   fidelity: **REPAIR** (PB-001: sync email blocks the request thread) · target: email dispatch
   must be enqueued, not sent in-request — see WO-002 · evidence:
   `legacy/app/server.py:69-76`, `legacy/app/notify.py:1-7`
3. Response: `{"closed": <bool>}` — `true` if this call performed the transition, `false` if the
   ticket was already closed (or, per the read-path quirk, the row didn't exist — see
   confidence note below).
   fidelity: FIXED · evidence: `legacy/app/server.py:73,77`
4. **Confidence note (inferred, not directly cited)**: closing a nonexistent `id` also returns
   `{"closed": false}` with `200` — the `UPDATE ... WHERE id = ?` simply matches zero rows,
   there's no existence check. Inferred from reading the query, not from a trace.
   fidelity: FIXED · confidence: inferred · evidence: `legacy/app/server.py:69-77`

## GET /internal/export/csv — export

1. Dumps ALL tickets as CSV (`id,title,status` columns only — no priority, dates, or
   assignee), `Content-Type: text/csv`, no auth/access control of any kind despite the
   `/internal/` path prefix.
   fidelity: FIXED · evidence: `legacy/app/server.py:111-115`
2. Comment: "written for the 2020 audit; no caller since." Static-only signal (no traffic data
   available) that this route may be unused — see `usage-weights.json` (down-weighted, not
   zeroed) and OQ-006-adjacent reasoning (not itself an OQ; kept as FIXED, low-priority WO).
   fidelity: FIXED · confidence: cited (comment) · evidence: `legacy/app/server.py:112`

## Cross-cutting

- No authentication or authorization exists on ANY route in this feature (or the whole app) —
  every endpoint including `/internal/export/csv` is open. Not a problem-brief entry (not
  reported), and not obviously in-scope for a "known problems: sync email + MD5 tokens" brief —
  left as FIXED (unauthenticated) rather than invented as a REPAIR. If this matters, it needs a
  human ruling, not a generator guess — flagged for gate review in the backlog (P8), not filed
  as a new OQ, since it applies uniformly to the whole app rather than one ambiguous behavior.
