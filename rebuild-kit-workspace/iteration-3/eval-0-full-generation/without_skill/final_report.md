## Summary

I set up the complete `ticketd` rewrite workspace under `ticketd/docs/superpowers/`, and — since this ran without anyone available to answer questions — actually built and ran the plan's code against a real local Postgres instance to validate it, rather than just writing it down.

**Artifacts produced** (all in `ticketd/docs/superpowers/`):
- **`specs/2026-08-09-ticketd-rewrite-design.md`** — design spec covering the async-notification fix (transactional outbox, not Celery/Redis), the reset-token redesign (`secrets.token_urlsafe` + SHA-256 hash storage), the slug-collision decision (DB-unique-constraint + numeric-suffix retry), the full API compatibility contract every route must preserve, and a "no Docker" fallback (see below). Includes an explicit **Open Questions** section (8 items) for things a real design conversation would have resolved — the access log's actual scope, the mystery `X-Internal-Bypass` header, cutover strategy, etc.
- **`plans/2026-08-09-ticketd-rewrite.md`** — 16-task TDD implementation plan, real working code per task (not pseudocode).
- **`verification/2026-08-09-ticketd-rewrite-verification.md`** — how to verify the rewrite, plus a record of what's actually been checked vs. still open.
- Updated `ticketd/README.md` to point future sessions at the workspace.

**What I actually validated this session** (not just claimed): built the full plan in a scratch directory, stood up a real local Postgres 16 cluster (Docker's daemon was unreachable in this sandbox, so I used `initdb`/`pg_ctl` directly — documented as a fallback), ran all 38 planned tests against it (all passed), and replayed the entire 2000-line `ops/access.log` against the running new API (2000/2000 handled cleanly). Fixed one real bug found in the process (a Pydantic v2 deprecation in the settings class). Scratch files were cleaned up; only the docs and README edit remain in the repo.

**Key finding worth flagging**: `ops/access.log` isn't actually a 30-day log — it's a 33-minute, single-user sample. I used it for *shape* (which endpoints matter, error/rate-limit patterns) but flagged everywhere that traffic-volume assumptions (pool sizing, concurrency) shouldn't be trusted from it.

**Limitations / things I couldn't verify**: no real SMTP server, no real `db/ticketd.sqlite3` to migrate (only a synthetic fixture), Alembic autogeneration wasn't actually run (used `create_all` as a stand-in), and Docker-based test setup is unverified in this environment. All noted in the verification doc.

I left the changes **uncommitted** — only README.md and the new `docs/` tree are staged/untracked, nothing else touched. Let me know if you'd like me to commit them.