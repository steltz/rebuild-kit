# ticketd Rewrite — Verification Plan

**Date:** 2026-08-09
**Companion to:** `docs/superpowers/specs/2026-08-09-ticketd-rewrite-design.md`,
`docs/superpowers/plans/2026-08-09-ticketd-rewrite.md`

This doc is the answer to "how do we know the rewrite is actually done and
correct." It was validated during this same session by actually building
the plan's code in a scratch directory and running it against a real local
Postgres instance — not just reasoned about. Results are recorded in §6 so
whoever picks this up next knows what's already been checked and what
hasn't.

## 1. Standing up Postgres for tests

The plan's `docker-compose.test.yml` (Task 1) is the intended path. In
**this** execution environment, two things didn't work and one did:

- `docker ps` hung indefinitely (~120s) with no response — the Docker
  daemon does not appear to be running/reachable here, even though the
  `docker` CLI is installed (`Docker version 28.1.1`).
- `brew services start postgresql@16` failed (`launchctl bootstrap` exited
  5, "Input/output error") — this sandbox's launchd access is restricted.
- **What worked:** running `initdb` + `pg_ctl` directly against a scratch
  data directory, bypassing both Docker and launchd:

```bash
export PGDATA=/tmp/ticketd_pgdata
/opt/homebrew/opt/postgresql@16/bin/initdb -D "$PGDATA" -U ticketd --auth=trust -E UTF8
/opt/homebrew/opt/postgresql@16/bin/pg_ctl -D "$PGDATA" -l /tmp/pg.log -o "-p 5432 -k /tmp" start
/opt/homebrew/opt/postgresql@16/bin/psql -h /tmp -U ticketd -d postgres -c "ALTER USER ticketd WITH PASSWORD 'ticketd';"
/opt/homebrew/opt/postgresql@16/bin/psql -h /tmp -U ticketd -d postgres -c "CREATE DATABASE ticketd_test;"
/opt/homebrew/opt/postgresql@16/bin/psql -h /tmp -U ticketd -d postgres -c "CREATE DATABASE ticketd;"
# stop when done:
/opt/homebrew/opt/postgresql@16/bin/pg_ctl -D "$PGDATA" stop -m fast
```

**Whoever executes the plan should try `docker compose up` first** (a
normal dev machine or CI runner likely has a working daemon, unlike this
sandbox) **and fall back to the `initdb`/`pg_ctl` recipe above only if
Docker isn't available.** Either way, the tests just need
`TICKETD_TEST_DATABASE_URL` pointing at a reachable, disposable Postgres —
they don't care how it got there.

## 2. Automated test suite (per plan Tasks 1–15)

Run: `TICKETD_TEST_DATABASE_URL=postgresql+asyncpg://ticketd:ticketd@localhost:5432/ticketd_test pytest -v`

Expected: every test file the plan creates passes. As of this session,
running the plan's exact code against a real local Postgres instance
produced:

```
38 passed in 0.63s
```

covering: schema round-trip, slug collision (no-collision / 2-way / 3-way),
`GET /api/tickets` (ordering, status filter), `GET /api/tickets/<id>`
(found / 200-empty-object-on-missing), `POST /api/tickets` (title
required, priority normalization both string and numeric-code forms, slug
collision), notification outbox enqueue, `POST .../close` (enqueues,
idempotent, fast), reset-token generation/hashing, `POST /api/auth/reset`
(creates token, rate limit, bypass header), `POST /api/auth/reset/confirm`
(valid, unknown, expired-identical-to-invalid), CSV export, the two
explicit SMTP-outage regression tests, the worker's send/fail/give-up
behavior, and the SQLite→Postgres migration script's slug de-duplication.

This is the primary correctness gate. If a future change makes any of
these fail, treat it as a regression against the documented API contract
(spec §4) unless the spec itself is being deliberately revised.

## 3. Access-log replay smoke test (per plan Task 15)

Run:
```bash
uvicorn app.main:app --port 8010 &
python -m ops.verify.replay_access_log --base-url http://localhost:8010 --log-path ops/access.log
```

Expected and **confirmed this session**: `replayed: 2000 ok, 0 failed` —
every request pattern in the sample log gets a non-5xx response from the
rewritten backend. Remember (spec §3): this is a shape check, not a load
test. It tells you the new backend *handles* every logged request pattern
without crashing; it says nothing about throughput or concurrency, because
the sample log isn't real traffic-volume data.

## 4. Migration verification (per plan Task 14, spec §9)

Beyond the unit test in `tests/test_migration.py` (which is a synthetic
2-row fixture, already passing per §2), verification against the **real**
`db/ticketd.sqlite3` before cutover should check:

1. **Row counts match.** `SELECT COUNT(*) FROM tickets` /
   `FROM users` in SQLite equals the post-migration counts in Postgres.
2. **Zero duplicate slugs post-migration.**
   `SELECT slug, COUNT(*) FROM tickets GROUP BY slug HAVING COUNT(*) > 1`
   against the migrated Postgres table must return no rows — this is the
   whole point of the slug-collision fix (spec §5), so it's worth checking
   explicitly rather than trusting the migration script blindly.
3. **Spot-check a sample of tickets field-for-field** (title, priority,
   status, timestamps) between source and destination — pick ~20 tickets
   spanning old and recent `created_at` values.
4. **Confirm `reset_tokens` starts empty** in Postgres post-migration
   (spec §9 — intentionally not migrated).
5. **Confirm the migration is re-run-safe / deterministic**: run it twice
   against two fresh copies of the same source SQLite file and diff the
   resulting `tickets.slug` assignments — they should be identical, since
   `ops/migrate_sqlite_to_postgres.py` resolves collisions in `id` order
   deterministically (already exercised by the unit test, but worth
   reconfirming against the real dataset's actual collision patterns,
   which the synthetic fixture can't represent).

## 5. Security-specific checks (spec §7)

These aren't exercised by the functional test suite in §2 and need an
explicit look, ideally by whoever flagged the original MD5 issue:

1. **No raw reset token is ever persisted.** `SELECT token_hash FROM
   reset_tokens LIMIT 5` — confirm every value is a 64-char hex string
   (sha256 digest), never the token itself. (`tests/test_auth_reset.py`
   already asserts `len(token_hash) == 64` as a proxy for this, but a
   human security read of the actual stored values pre-launch is still
   worth doing.)
2. **Token entropy.** `secrets.token_urlsafe(32)` is 256 bits — confirm
   this wasn't quietly reduced anywhere between spec and implementation
   (`app/security.py::generate_reset_token`).
3. **Expiry is enforced server-side at confirm time**, not just
   client-displayed — `tests/test_auth_confirm.py::
   test_confirm_expired_token_returns_identical_body_to_invalid` covers
   this, confirm it stays in the suite.
4. **Rate limiting and the `X-Internal-Bypass` header** — confirm the
   bypass header's behavior matches spec exactly (unchanged from legacy)
   and flag it to whoever owns app security per spec Open Question 2; this
   rewrite doesn't change it, but it's a good moment to ask if it still
   needs to exist.

## 6. What's been verified this session vs. what's still open

**Verified (code actually run against real Postgres, this session):**
- Every file in plan Tasks 1–15 compiles and imports cleanly.
- All 38 planned tests pass against a real Postgres 16 instance (not
  SQLite-in-memory standing in for Postgres, except for `app/worker.py`
  and `ops/migrate_sqlite_to_postgres.py`'s tests, which by design use a
  sync engine and don't need Postgres specifically — see plan Task 12).
- The `pydantic-settings` `class Config:` pattern in the original plan
  draft is deprecated in Pydantic v2 (produces a `PydanticDeprecatedSince20`
  warning); the plan was corrected in place to use `SettingsConfigDict` /
  `model_config` before this doc was finalized. If you're implementing
  from a plan version that still shows `class Config:`, use
  `SettingsConfigDict` instead.
- The access-log replay smoke script runs clean end-to-end against the
  real `ops/access.log`.

**Not verified this session (needs a human or a later run to confirm):**
- Alembic autogeneration was not actually run (plan Task 2, Step 4) — the
  scratch verification used `Base.metadata.create_all` directly, which
  exercises the same table/constraint definitions but doesn't prove the
  Alembic migration file itself is correct. Run `alembic revision
  --autogenerate` for real during Task 2 and hand-check the output before
  trusting it.
- The migration script (Task 14) was only exercised against a 2-row
  synthetic fixture, not against the real `db/ticketd.sqlite3`, which
  wasn't provided in this workspace (spec §9's checklist in §4 above is
  for whenever the real file becomes available).
- No real SMTP server was exercised — `app/worker.py`'s tests use fake
  SMTP clients (by design, per plan Task 12), so actual `smtp.internal`
  connectivity/credentials/deliverability are unverified. Confirm against
  a real or staging SMTP endpoint before cutover.
- Concurrency/load behavior — nothing in this session tested concurrent
  request handling under real traffic. Spec §3's caveat about the access
  log applies here too: don't assume the sample log's timing represents
  real load.
- Docker-based test setup (`docker-compose.test.yml`) was not actually
  exercised, since the Docker daemon wasn't reachable in this sandbox
  (§1) — the `initdb`/`pg_ctl` fallback was used instead and is what's
  confirmed working.

## 7. Acceptance checklist (maps back to the three original problems)

- [ ] **SMTP outage can no longer take down ticket closing.**
      `tests/test_smtp_outage_regression.py` passes, AND a manual check:
      point `TICKETD_SMTP_HOST` at an unreachable host/port, hit
      `POST /api/tickets/<id>/close`, confirm it still returns `200` in
      well under a second.
- [ ] **No MD5, no plaintext reset tokens.** §5 checks above pass against
      a real (not just test) Postgres instance.
- [ ] **No slug collisions possible.** `tickets.slug` has a Postgres
      `UNIQUE` constraint (verify via `\d tickets` in `psql`), and the
      migration produced zero duplicates (§4 check 2).
- [ ] **API contract unchanged.** Every quirk in spec §4 has a passing
      test, AND the access-log replay (§3) returns `0 failed`.
- [ ] **No UI changes required.** Confirm this by pointing the actual
      `svc-ui/2.1` client (or whatever currently serves the UI) at the new
      backend in a staging environment and clicking through the golden
      paths (list tickets, create, close, request/confirm a reset) — none
      of this session's automated checks can substitute for that, since
      there's no UI source in this workspace to test against directly.
