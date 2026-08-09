# Draft — Tickets subsystem

<!-- P4 draft, self-verified against legacy/app/server.py line-by-line on 2026-08-09.
     Confidence: all claims below are `cited` (file:line). None are `traced` (no runtime
     capture available this run — rebuild.json.evidence.trace_capture_t1 = inactive). -->

## Feature: List tickets — `GET /api/tickets`

- statement: Returns all tickets as a JSON array, optionally filtered by exact `status` match
  via `?status=` query param, always ordered `created_at DESC`.
  fidelity: FIXED
  evidence: legacy/app/server.py:27-37 (cited)
- statement: No pagination exists; every matching row is returned in one response. In-code
  comment states this is relied upon: "the UI relies on getting everything and filtering
  client-side" (legacy/app/server.py:35).
  fidelity: FIXED
  evidence: legacy/app/server.py:35-37 (cited)
- statement: `status` filter does exact string match against the DB `CHECK` domain
  (`open`/`closed`); an unrecognized status value returns an empty array (no validation error),
  since it just yields zero SQL matches.
  fidelity: FIXED
  evidence: legacy/app/server.py:29-36, legacy/db/schema.sql:6 (cited, inferred from SQL
  semantics — no explicit validation branch)

## Feature: Create ticket — `POST /api/tickets`

- statement: `title` is required (after `.strip()`); missing/blank/whitespace-only title returns
  `422 {"error": "title_required"}`.
  fidelity: FIXED
  evidence: legacy/app/server.py:42-45 (cited)
- statement: `priority` accepts either the string domain values (`"low"`/`"med"`/`"high"`) or the
  numeric-string codes `"1"`/`"2"`/`"3"` (mapped 1→low, 2→med, 3→high); any other value is passed
  through as-is to the DB `CHECK` constraint and would raise a DB error (uncaught — no
  try/except around the insert).
  fidelity: FIXED
  evidence: legacy/app/server.py:46-51 (cited)
- statement: Defaults `priority` to `"med"` when absent from the request body.
  fidelity: FIXED
  evidence: legacy/app/server.py:47 (cited)
- statement: New tickets are always created with `status='open'` — no way to create
  pre-closed.
  fidelity: FIXED
  evidence: legacy/app/server.py:51 (cited)
- statement: `slug` is computed via `slugify(title)` and stored at insert time, then
  *recomputed* (not re-read from the row just inserted) for the response body — both calls use
  the same input so they agree, but it's two separate slugify() calls, not one value reused.
  fidelity: FIXED
  evidence: legacy/app/server.py:51,55 (cited)
- statement: `created_at` is `datetime.now().isoformat()` — naive local server time, no
  timezone offset recorded. Flagged in-code with `# naive local time!` (legacy/app/server.py:52).
  fidelity: FIXED — not in the problem brief, so not a REPAIR target. Carrying forward exactly
  (including the naive-time behavior) unless a human ruling promotes this to a PB entry.
  evidence: legacy/app/server.py:52 (cited)
- statement: Success response is `201 {"id": <int>, "slug": <str>}` — the response does **not**
  echo `title`, `priority`, `status`, or `created_at`.
  fidelity: FIXED
  evidence: legacy/app/server.py:55 (cited)
- statement: Slug collisions between distinct tickets are possible and unhandled (no uniqueness
  check, no DB constraint) — two tickets titled "Fix DB" and "fix db!" get the identical slug
  `fix-db`.
  fidelity: FIXED (existing, evidenced behavior — not brief-flagged, so not REPAIR). If this
  should change, it needs a human ruling; proposed as a PB-proposal candidate, not decided here.
  evidence: legacy/app/util.py:5-6, legacy/db/schema.sql:1-10 (cited — schema has no UNIQUE on
  slug)

## Feature: Get single ticket — `GET /api/tickets/<int:tid>`

- statement: Non-integer `tid` in the URL path doesn't match the Flask `<int:tid>` converter and
  falls through to Flask's default 404 HTML error page (not this app's JSON error shape) — this
  is Flask routing behavior, not app logic, but is an observable difference from the "empty
  object" 200 case below.
  fidelity: FIXED
  evidence: legacy/app/server.py:58 (cited, inferred from Flask's `<int:...>` converter
  semantics — no explicit test of this path in the tree)
- statement: A well-formed but nonexistent `tid` returns `200 {}` — explicitly NOT a 404 — because
  "the legacy UI depends on it" per the in-code comment.
  fidelity: FIXED — this is the one place the legacy code itself declares intent behind an
  otherwise-surprising behavior; treat as load-bearing, not a bug to silently fix.
  evidence: legacy/app/server.py:59-63 (cited)
- statement: An existing ticket returns `200` with the full row as a flat JSON object (all
  columns, including `assignee_id` even though nothing ever sets it, and `closed_at` which is
  `null` for open tickets).
  fidelity: FIXED
  evidence: legacy/app/server.py:64, legacy/db/schema.sql:1-10 (cited)

## Feature: Close ticket — `POST /api/tickets/<int:tid>/close`

- statement: Closing sets `status='closed'` and `closed_at=now()`, but only if the ticket is not
  already closed — the UPDATE's WHERE clause includes `AND status != 'closed'`, making repeat
  closes a no-op on the row (idempotent update, but see response-shape note below).
  fidelity: FIXED
  evidence: legacy/app/server.py:69-71 (cited)
- statement: Closing a nonexistent `tid` is indistinguishable from closing an already-closed
  ticket at the response level — both yield `rowcount=0` → `{"closed": false}`, `200`. No 404
  case exists for this route.
  fidelity: FIXED
  evidence: legacy/app/server.py:69-77 (cited, inferred — no explicit existence check, follows
  from `rowcount` semantics)
- statement: Response body is `{"closed": <bool>}` reflecting whether *this call* performed the
  transition (`rowcount > 0`), not whether the ticket's current status is closed.
  fidelity: FIXED
  evidence: legacy/app/server.py:77 (cited)
- statement: On a successful transition (and only then), sends a synchronous notification email
  to the hardcoded address `watchers@example.internal` with body `f"closed: {title}"`, blocking
  the request on SMTP (2s typical, up to 30s timeout per `app/notify.py`'s own docstring).
  fidelity: **REPAIR** — PB-001. Target: dispatch this notification asynchronously (mechanism
  FREE, see WO-004 and `docs/open-questions.md#OQ-002`); the close endpoint's response must not
  wait on SMTP.
  evidence: legacy/app/server.py:73-76, legacy/app/notify.py:1-7 (cited)   divergence: pending
  ED entry once OQ-002 is ruled (P8/P9)
- statement: The notification recipient is a single hardcoded address with no per-ticket/per-team
  "watcher" concept modeled anywhere (no table, no route to manage it).
  fidelity: FIXED (existing, evidenced) — carried forward as-is; not brief-flagged, so not
  REPAIR, even though "watcher" as a concept looks unfinished. See `docs/domain/glossary.md`.
  evidence: legacy/app/server.py:76 (cited)
