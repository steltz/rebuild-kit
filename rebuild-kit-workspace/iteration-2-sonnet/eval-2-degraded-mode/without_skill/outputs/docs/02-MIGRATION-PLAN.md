# Migration Plan

Phased so that work usable today (code, schema, tests) doesn't wait on
evidence we don't have yet (git history, access logs, prod DB access "in a
few weeks" per the handover). Each phase names what unblocks it.

## Phase 0 — Done in this pass (no evidence required)

- FastAPI + Postgres rewrite of every endpoint in `ticketd/app/server.py`,
  behavior-for-behavior, in `./rewrite`.
- Fixed the two named problems (sync email → outbox; MD5 tokens → hashed
  random tokens).
- Documented every other code-level observation instead of acting on it
  (`docs/01-LEGACY-BEHAVIOR-INVENTORY.md`).
- Parity test suite (`rewrite/tests/`) — not yet run against installed
  dependencies or real Postgres (no environment was available during
  generation; see `rewrite/README.md`).

**Not done, and shouldn't be attempted without evidence:** a data migration
script. See Phase 2.

## Phase 1 — Unblocked by git history / access logs (evidence, no DB needed)

Goal: turn every "preserved because we don't know" item in the behavior
inventory into either "confirmed safe to fix" or "confirmed load-bearing,
keep."

1. Pull git history (even a partial `git log --follow` on each file, or
   whatever the contractor can produce) to explain:
   - The trailing `# tweak 1/2/3` comments in `server.py`.
   - Whether the two named problems were ever partially addressed before
     and reverted (informs whether there's a reason the "obvious" fix
     applied here was avoided previously).
2. Pull access/request logs (even a sample) to answer, per row in
   `docs/03-OPEN-QUESTIONS-AND-RISK-REGISTER.md`:
   - Is `GET /api/tickets` actually called without pagination at a scale
     that matters, or is ticket volume small enough it doesn't matter?
   - Does anything send `X-Internal-Bypass: 1`? From where? Is it a
     legitimate internal service or should it be removed/replaced with real
     auth?
   - Has `/internal/export/csv` been called at all since 2020, per the
     original author's comment?
   - Does the legacy UI genuinely depend on `GET /api/tickets/{id}`
     returning `200 {}` for a missing ticket, or was that comment stale?
3. Update `docs/01-LEGACY-BEHAVIOR-INVENTORY.md` with findings and, only
   then, change the corresponding rewrite behavior with a clear commit
   message citing the evidence.

## Phase 2 — Unblocked by production DB access ("in a few weeks")

1. **Row counts and data-quality read** of `tickets`, `users`,
   `reset_tokens` against the real SQLite file: null rates, actual priority
   values in use (confirms/refutes the "clients send both formats" comment),
   duplicate slugs (quantifies the collision risk noted in the behavior
   inventory), orphaned `assignee_id`s.
2. **Write and test the actual migration script** (SQLite → Postgres) against
   a snapshot/copy of production data, not synthetic data. It needs to:
   - Backfill `users` and `tickets` as direct copies (column-compatible).
   - **Not** migrate `reset_tokens` rows — they're MD5-derived, live for at
     most `RESET_WINDOW_MIN` (30 min), and the new schema stores a hash of a
     different token scheme entirely. Any tokens in flight at cutover expire
     naturally; migrating them would be meaningless (there's no way to
     recover the plaintext to hash it) and would import known-weak
     identifiers into the new store for no benefit.
   - Convert `created_at`/`closed_at` from naive-local strings to
     `TIMESTAMPTZ`. This requires knowing the server's actual timezone at
     write time — not yet confirmed; do not assume UTC without checking.
   - Decide, with real duplicate-slug counts in hand, whether to accept
     collisions as-is or add a disambiguating suffix during import.
3. **Dry-run cutover** against the migrated copy: run the parity test suite
   from `rewrite/tests/` against the migrated Postgres instance, then run
   the legacy Flask app and the new FastAPI app side by side against
   equivalent seed data and diff responses for the endpoints in the
   behavior inventory.
4. **Cutover.** Stop the legacy app, run the tested migration script once,
   start the FastAPI app + `app.worker`, verify `/healthz` and one write
   (create + close a ticket) end-to-end.

## Fixes Applied (summary, cross-referenced from README)

| Problem | Legacy | Rewrite |
|---|---|---|
| Sync email blocks requests | `smtplib` call inline in the request handler (`server.py:76,94`) | Transactional outbox (`notification_outbox` table) + separate poller (`app/worker.py`) |
| MD5 reset tokens | `hashlib.md5(email + time.time())`, stored in plaintext (`server.py:90`) | `secrets.token_urlsafe(32)`, only SHA-256 hash persisted |

No other behavior was changed. See `docs/01-LEGACY-BEHAVIOR-INVENTORY.md`.
