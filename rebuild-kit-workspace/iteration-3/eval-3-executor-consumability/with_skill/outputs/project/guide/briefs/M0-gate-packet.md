# Gate: Milestone 0 — walking skeleton (WO-001)

**What this is.** Per root `CLAUDE.md`'s executor loop step 7, WO-001 is a gated work order
(`gate: true`, risk 0.55 — "this WO's FREE choices become the substrate every later WO builds
on; a bad call here is expensive to unwind"). Implementation is complete and green; this packet
requests the human sign-off `backlog.md` requires before Milestone 1 starts. `ledger.json`
records WO-001 as `awaiting_gate_approval`, not `done` — that flip happens when this gate is
approved (`gate_approved_by` + `approved_at` on the M0 milestone entry).

## What was built

`modern/` now has a real FastAPI + Postgres app implementing `GET /api/tickets` and
`POST /api/tickets` (the two highest-traffic routes, 0.829 combined usage weight), plus the
project skeleton every later WO inherits: SQLAlchemy 2.x models, Alembic migrations, a
Pydantic schema layer, and a global exception handler. `verification/harness/run-modern.sh`
is a real implementation (no longer the generated stub) — it provisions a fresh, disposable
Postgres cluster per suite and boots the app against it. `verification/harness/drive_inputs.py`
was extended to dump Postgres state (previously sqlite-only) and a latent header-casing bug in
its HTTP client was fixed (see "Found while executing" below).

## Verification results

| Level | Result |
|---|---|
| L1 (contract) | **pass** — `docs/contracts/validate_fixtures.py`, 6/6 fixtures against `openapi.yaml` |
| L2 (characterization) | **pass, in-scope** — `verification/characterization/test_against_golden.py`: tickets-list 4/4, tickets-create 8/8, run against a fresh `modern/` boot. Running the *entire* golden set (all suites, including ones no WO has implemented yet) in one shared L2 session shows additional failures — traced to `admin-export-csv`'s own golden traces calling the now-live `POST /api/tickets` and shifting the id sequence before `tickets-create`'s cases run. This is L2's documented lack of per-suite isolation (`test_against_golden.py`'s own docstring: state diffing is L3-only, L2 shares one live instance), not a `modern/` defect — confirmed by re-running each suite alone on its own fresh boot, where all cases pass. |
| L3 (acceptance oracle) | **pass** — `verification/harness/diff-run.sh tickets-list` (4/4) and `diff-run.sh tickets-create` (8/8), both including full `state.db_dump` parity across `tickets`/`users`/`reset_tokens`. |

Reproduce: `verification/harness/diff-run.sh tickets-list && verification/harness/diff-run.sh tickets-create` (requires `modern/.venv` with `modern/requirements.txt` installed, and Postgres client+server binaries — `initdb`/`pg_ctl`/`createdb`/`psql` — on `PATH`; see `verification/harness/README.md`).

## Found while executing (P7-style: only surfaces by actually running the app)

- **`drive_inputs.py`'s `send()` had a case-sensitive `Content-Type` header lookup.** It built
  a plain `dict` from the response headers and did `.get("Content-Type", "")`, which silently
  missed uvicorn's lowercase `content-type` header (Werkzeug's dev server happens to emit
  title-case, so this never surfaced against legacy). The miss caused JSON response bodies to
  be treated as opaque non-JSON text on every single modern/ response — every L3 diff failed
  with body-shape mismatches before this fix. Fixed by using the underlying
  `email.message.Message`'s native case-insensitive `.get()` instead of a plain dict. This is
  shared harness infrastructure, not modern/-specific, so it benefits every future WO's L3 runs
  too.
- **Postgres sequences are non-transactional.** A rolled-back insert (e.g. the invalid-priority
  500 case) still consumes a sequence value, unlike SQLite's rowid. This does not affect
  WO-001's replay suites because `tickets-create.jsonl`'s invalid-priority case is deliberately
  ordered last (originally for an unrelated reason — legacy's OQ-010 connection-leak bug) — but
  it's a real behavioral difference from legacy worth flagging for whoever next writes a suite
  where a failed create is *not* the last write in the sequence. Not filed as an OQ since it
  doesn't affect any WO's acceptance criteria today; noted here for visibility.

## FREE choices made (full detail in `ledger.json` → `work_orders[WO-001].free_choices`)

ORM/driver (SQLAlchemy 2.x + psycopg3, sync session), migrations (Alembic), layout
(`modern/app/{api,models.py,schemas.py,services,db.py}`), error handling (a single app-wide
`Exception` handler reproducing Werkzeug's default 500 page byte-for-byte, rather than
special-casing the one known trigger), the `POST /api/tickets` handler deliberately bypassing
Pydantic body validation so the two P9-audit gaps (non-dict body, null/non-string title →
uncaught 500) reproduce exactly, timestamps (`TIMESTAMPTZ`, UTC-aware, per `modern/CLAUDE.md`'s
default pending OQ-003), and `reset_tokens`/`users` kept as legacy-shape mirrors (untouched by
this WO) purely so replay state-diffing has matching tables on both sides.

## Known limitations / carried-forward gaps (not blockers for this gate)

- `reset_tokens` pre_sql seeding (raw SQL fixture injection) against a postgres DSN is not
  implemented in `drive_inputs.py` — raises `NotImplementedError` rather than silently
  mis-seeding. No WO-001 suite needs it; flagged for whichever WO first does (likely
  WO-003/WO-008's `auth-reset-confirm` suite).
- OQ-001 (slug collision mechanism) and OQ-002 (auth/proxy identity) remain unruled, as
  expected — WO-001 was written to be answerable either way and doesn't touch either question.

## M0 close criteria (`backlog.md`) — status

- [x] `verification/harness/run-modern.sh` implemented (no longer the generated stub)
- [x] `diff-run.sh tickets-list` and `diff-run.sh tickets-create` both green
- [x] `modern/CLAUDE.md`'s FREE choices recorded in `ledger.json`
- [ ] **Human sign-off** — this packet

---
Ruling: ____________  Approved by: ________  Date: ______
(Recording approval in `ledger.json` — `milestones[M0].approved_by`/`approved_at` and
`work_orders[WO-001].gate_approved_by` — is what unblocks Milestone 1.)
