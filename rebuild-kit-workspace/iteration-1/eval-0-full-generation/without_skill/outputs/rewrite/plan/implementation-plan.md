# Implementation plan

Phased so that every phase ends green and reviewable. Execute phases in order; tasks inside
a phase are ordered but 2/3/4 can partially interleave once Phase 1 is done. Before
starting, read `decisions/open-questions.md` — Q1 gates task 2.6, Q5 gates 5.2.

Follow TDD throughout: for each endpoint, port/enable its contract tests from
`../verification/contract_tests/` first, watch them fail, then implement.

## Phase 0 — Scaffold `../ticketd-ng/`

- 0.1 Repo layout:
  ```
  ticketd-ng/
    app/
      __init__.py
      main.py          # FastAPI app factory, exception handlers
      config.py        # pydantic-settings: DATABASE_URL, SMTP_HOST/PORT, MAIL_FROM,
                       # WATCHERS_ADDR, RESET_WINDOW_MIN=30, RESET_RATE_LIMIT_PER_HOUR=3,
                       # RESET_RATE_BYPASS_ENABLED=false, SMTP_TIMEOUT=30
      db.py            # async engine/session
      models.py        # SQLAlchemy models (03-data-model.md)
      routes/tickets.py
      routes/auth.py
      slug.py          # port of legacy slugify, byte-identical output
      outbox.py        # enqueue helper
      worker.py        # python -m app.worker
    alembic/           # baseline migration = 03-data-model.md
    scripts/migrate_from_sqlite.py   # Phase 5
    tests/             # unit tests; contract tests stay in rewrite/verification
    docker-compose.yml # postgres:15 + optional mailpit/smtp4dev for local SMTP
    pyproject.toml
  ```
- 0.2 `docker-compose up` gives Postgres; `uvicorn app.main:app` serves `GET /healthz`.
- 0.3 CI-able commands: `pytest`, `alembic upgrade head`, `ruff check`.
- **Done when:** healthz test passes against a fresh checkout with one command sequence
  documented in ticketd-ng/README.

## Phase 1 — Schema

- 1.1 Alembic baseline exactly per `specs/03-data-model.md` (including outbox and the
  partial index; **no** slug unique index — Q1).
- 1.2 SQLAlchemy models + a fixture that spins schema onto a test DB.
- **Done when:** `alembic upgrade head` on empty DB matches the spec (`pg_dump -s` review).

## Phase 2 — Ticket endpoints (wire-compatible)

- 2.1 Custom error handling: legacy-shaped bodies (`{"error": ...}`), never FastAPI's
  `{"detail": ...}` on contract endpoints; non-integer `{id}` → 404 (inventory 3.3).
- 2.2 `GET /api/tickets` — list, `?status=` filter, `created_at DESC, id DESC`, no
  pagination (1.1–1.4).
- 2.3 `POST /api/tickets` — manual body parsing (2.2), title validation (2.1), priority
  normalization incl. numeric forms (2.3), 422 `invalid_priority` for junk (2.4), 201
  `{"id","slug"}` (2.6), extra keys ignored (2.8).
- 2.4 `GET /api/tickets/{id}` — found → full object; missing → **200 `{}`** (3.2).
- 2.5 `POST /api/tickets/{id}/close` — transactional close + outbox insert (4.1–4.5);
  `{"closed": bool}`; no outbox row when already closed/nonexistent.
- 2.6 **[GATED on Q1]** Slug collision policy. Default (recommendation A): unique index on
  slug, suffix `-2`, `-3`… on collision inside a retry loop. Until Q1 is resolved, slugs
  behave exactly like legacy (collisions allowed) and tests marked `xfail_q1` stay skipped.
- **Done when:** contract suite sections T1–T4 pass against ticketd-ng; T1–T4 minus the
  known CHANGE rows also pass against legacy ticketd (proves the tests, not just the app).

## Phase 3 — Reset flow

- 3.1 Token service per `specs/05-security-reset.md` (secrets.token_urlsafe(32), sha256 at
  rest, atomic consume via UPDATE...RETURNING).
- 3.2 `POST /api/auth/reset` — rate limit 3/h/email (429), config-gated bypass header (Q2),
  always 200 `{"ok": true}`, outbox enqueue `reset token: <token>`.
- 3.3 `POST /api/auth/reset/confirm` — 403 `{"error":"invalid_token"}` for
  wrong/expired/used; 200 `{"ok": true, "email": ...}`.
- 3.4 Token cleanup job (>24 h) — piggyback on the worker loop.
- **Done when:** contract suite T5–T6 and the security checklist in
  `specs/05-security-reset.md` all pass; concurrency test (double-confirm) included.

## Phase 4 — Notification worker

- 4.1 `app/worker.py` per `specs/04-notifications.md`: SKIP LOCKED batch, backoff, MIME
  wrapper (Q9 default), config-driven SMTP.
- 4.2 Local SMTP sink (mailpit) in docker-compose; integration test asserts delivery and
  body text `closed: <title>` / `reset token: <token>`.
- 4.3 Outage test: stop the sink, close tickets (all 200 fast), start sink, assert
  drain — this is acceptance test V-6.
- **Done when:** V-6 passes and pending-outbox age query returns 0 in steady state.

## Phase 5 — Data migration

- 5.1 `scripts/migrate_from_sqlite.py` per `specs/03-data-model.md` (args: sqlite path,
  `--source-tz` (Q5/Q8), `--wipe-target`; refuses non-empty target otherwise).
- 5.2 Verification report (counts, id ranges, status/priority histograms, NULL-priority
  repairs, (id,title,status) checksum vs source).
- 5.3 Test against a synthetic SQLite file built from `ticketd/db/schema.sql` seeded with
  edge cases: colliding slugs, NULL priority, NULL assignee, closed-with-null-closed_at,
  unicode titles, 64-char slugs.
- **Done when:** report shows exact parity on the synthetic DB; script is idempotent-safe.

## Phase 6 — Cutover (needs Q4, Q7, Q8 answered)

- 6.1 Deploy ticketd-ng + worker to staging; run full contract suite + V-checklist there.
- 6.2 Freeze legacy writes → run migration against prod SQLite → verify report → point the
  gateway/svc-ui at ticketd-ng → smoke: create, list, get-missing (expect `{}`), close
  (expect email), reset round-trip.
- 6.3 Watch for 48 h: 500-rate (expect it to *drop* vs legacy ~2.5%, Q10), pending-outbox
  age, 429 rate. Legacy stays runnable (read-only) for instant rollback: repoint gateway
  back; any tickets created on ng during the window would need manual reconciliation —
  keep the window short.
- 6.4 After soak: decommission legacy; archive its sqlite file; close out open-questions
  resolutions.
- **Done when:** verification/verification.md is fully checked off and signed.

## Suggested session breakdown for Claude Code executors

One session per phase is comfortable; Phase 2 is the largest (can split 2.1–2.4 / 2.5–2.6).
Each session: read README → the relevant spec(s) → open-questions → implement with the
contract tests as the target. Update open-questions "Resolution" lines and check off
verification items as you go — these two files are the workspace's running state.
