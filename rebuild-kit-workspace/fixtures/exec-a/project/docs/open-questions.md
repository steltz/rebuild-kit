# Open Questions — ASK register & PB proposals

<!-- Executor + generator both append here. Never delete entries; rulings are appended.
     Each new OQ gets a ruling brief generated into guide/briefs/ (templates/ruling-brief.md).
     All entries below were raised during generation (P3/P4) since no human was available for
     interview during this run — see docs/problem-brief.md's "Open intake questions" for the
     narrative version of the same gaps. -->

## OQ-001 — What should happen when a new ticket's slug collides with an existing one?
- raised_by: generator P4 (from PB-003)
- kind: conflict / underspecified-fix
- readings:
  - A: Reject the create (422) and ask the client to disambiguate — matches how `title` is
    already validated, but changes response shape for a case the legacy app currently allows
    silently (creates evidence: `app/server.py:50-55`, no collision check exists at all today).
  - B: Auto-suffix the slug (`fix-db`, `fix-db-2`, ...) — outcome parity with "ticket gets
    created," changes only the derived field, lowest client-visible risk.
  - C: Include the ticket's own `id` in the slug (`fix-db-1042`) — guarantees uniqueness by
    construction, but changes the slug *format* for every ticket, not just colliding ones,
    which is a bigger visible change than A or B.
- blocks: [WO-005]
- ruling: PENDING

## OQ-002 — Does the FastAPI rewrite need to implement authentication, or does an upstream proxy handle it?
- raised_by: generator P3 (from problem-brief OIQ-4)
- kind: ambiguity
- readings:
  - A: No auth needed in `modern/` — an upstream reverse proxy already authenticates and the
    access log's populated user field (`jdoe@corp.example.com`, in the `%u`-style position) is
    evidence of that proxy's identity injection. Evidence: circumstantial only (log shape),
    nothing in the legacy tree confirms or denies a proxy's existence.
  - B: The legacy app is simply unauthenticated today (a real gap, possibly tolerated only
    because it's "internal") and the rewrite should add auth. Evidence: zero auth code found
    anywhere in `app/server.py` — every one of the 7 routes is reachable with no credential
    check, no session, no token verification.
- blocks: nothing outright (Milestone 0 is scoped to not require an answer), but flags gate
  review for every WO past M0 that touches request identity or session handling.
- ruling: PENDING

## OQ-003 — `created_at`/`closed_at` stored as naive local time — PB proposal
- raised_by: generator P4 (code smell, not brief-sourced)
- kind: pb-proposal
- readings:
  - A: Unintentional bug (the code comment `# naive local time!` at `app/server.py:52` reads
    like a developer flagging their own mistake, not documenting intended behavior) — the
    rewrite should store UTC-aware timestamps.
  - B: Intentional simplicity for an internal single-timezone tool — changing it is scope creep
    the brief never asked for (no PB entry mentions timestamps or timezones at all).
- blocks: nothing (modern/CLAUDE.md defaults to UTC pending this ruling; does not block other WOs)
- ruling: PENDING
  <!-- If ruled "intentional," this stays FIXED and modern/CLAUDE.md's UTC default is reverted
       for this field. If ruled "bug," add a PB entry, disposition REPAIR, before acting. -->

## OQ-004 — Is `GET /internal/export/csv` still needed by anyone?
- raised_by: generator P2 (zero-traffic report, low confidence — mirrors problem-brief OIQ-6)
- kind: inferred-only
- readings:
  - A: Dead — comment says "no caller since [2020]" and zero hits in the sampled log.
  - B: Still used, rarely (e.g. an annual audit) — a synthetic 1-hour log window cannot
    distinguish "dead" from "used yearly," and the comment is a developer's belief, not
    confirmed telemetry from the actual audit process.
- blocks: nothing outright; determines whether the route is a normal low-priority `FIXED` WO or
  a `do-not-port.md` entry.
- ruling: PENDING

## OQ-005 — Is `tickets.assignee_id → users.id` referential integrity actually enforced today?
- raised_by: generator P3 (domain recon, `docs/domain/ticket.md`)
- kind: discrepancy
- readings:
  - A: Yes, in practice, if the SQLite connection has foreign keys on — but
    `app/server.py:db()` never issues `PRAGMA foreign_keys = ON`, and SQLite defaults this
    OFF per connection, so the `REFERENCES users(id)` clause in `schema.sql:7` is very likely
    decorative today.
  - B: Enforcement happens elsewhere (a different code path not in this tree, or the SQLite
    build in use defaults it differently — version-dependent).
- blocks: nothing directly; matters for whether Postgres (which enforces FKs by default) should
  reproduce "declared but unenforced" (`FIXED`, if intentionally loose) or "enforced"
  (arguably a `REPAIR`-adjacent tightening nobody asked for). Affects `docs/contracts/ddl.sql`
  and the migration census (P6) — orphaned `assignee_id` rows may exist precisely because
  nothing ever stopped them.
- ruling: PENDING

## OQ-006 — Is the `X-Internal-Bypass: 1` reset-rate-limit bypass header intentional?
- raised_by: generator P4 (`docs/domain/reset_token.md`) — this is the schema.md worked example,
  confirmed present in the actual codebase, not a hypothetical
- kind: ambiguity
- readings:
  - A: Legitimate internal-tooling bypass (some internal caller needs to send >3 resets/hour on
    behalf of users, e.g. a support console) — evidence: it's a deliberate, specific string
    check (`server.py:84`), not an accident.
  - B: A forgotten debug/test backdoor that should not exist in a security-sensitive rate limit
    — evidence: completely undocumented (no README mention, no comment explaining it, not
    gated by any additional auth check of its own).
- blocks: nothing outright; flags gate review for WO-003 (reset flow REPAIR) since the mechanism
  is being rebuilt anyway and this is the natural point to decide whether the bypass survives.
- ruling: PENDING

## OQ-007 — How is the `users` table populated, if no route in this codebase writes to it?
- raised_by: generator P3 (`docs/domain/user.md`)
- kind: inferred-only
- readings:
  - A: An admin tool or direct DB access outside this repo — the migration plan (P6) needs to
    know where those rows will come from post-migration if so.
  - B: Vestige of a removed feature; `users` (and by extension `tickets.assignee_id`) may be
    safe to treat as legacy structure with no live population path going forward.
- blocks: nothing in Tickets/Auth WOs directly; blocks a confident `docs/migration/mapping.md`
  policy for the `users` table (P6 currently marks it ASK for exactly this reason).
- ruling: PENDING

## OQ-008 — Where does password changing actually happen? No route in this tree does it.
- raised_by: generator P4 (`docs/domain/glossary.md`)
- kind: inferred-only
- readings:
  - A: A separate service/system owns password storage and verification; `confirm_reset`
    handing back `{"email": ...}` is the handoff point — some other component (not in scope
    here) takes that confirmed-email signal and lets the user set a new password.
  - B: This is dead/partial functionality — the reset flow was built and the password-change
    half was never finished or was removed, and nobody has noticed because `{"ok": true,
    "email": ...}` still "looks like success" to any client that doesn't check further.
- blocks: nothing directly (WO-003 REPAIRs the token mechanism regardless of which reading is
  true — the API contract `{"ok": true, "email": ...}` is `FIXED` either way per PB-005).
  Matters only if the rewrite is ever asked to go further than "REPAIR the token," which no PB
  entry currently asks for.
- ruling: PENDING

## OQ-009 — Should `POST /api/auth/reset/confirm` gain rate limiting? — PB proposal
- raised_by: generator P4 (`docs/features/draft/auth-reset-confirm.md`)
- kind: pb-proposal
- readings:
  - A: Yes — unlimited token-guessing attempts within the 30-minute window is a real gap,
    independent of PB-002's token-strength fix; defense in depth is good practice regardless.
  - B: No — once WO-003 replaces the MD5 token with a CSPRNG-generated one, brute-forcing
    becomes computationally infeasible and rate limiting here adds complexity for negligible
    marginal security benefit; the brief never named this as a problem.
- blocks: nothing (WO-003 can close without this — it's an addition, not a fix to a stated
  defect, so it stays out of WO-003's scope unless ratified here first)
- ruling: PENDING

## OQ-010 — Legacy leaks DB connections on error paths, causing cascading "database is locked" — PB proposal
- raised_by: generator P7 — discovered by actually booting legacy and driving real requests
  through the harness (verification/harness/), not by static reading. Highest evidence tier:
  traced, reproduced twice independently.
- kind: pb-proposal
- readings:
  - A: Genuine bug, worth a PB entry and a REPAIR target. `app/server.py:db()` opens a
    `sqlite3.connect()` per request into Flask's `g` but the app registers no
    `@app.teardown_appcontext` to close it. When a request raises before reaching `.commit()`
    (e.g. `tickets-create-invalid-priority`, PB-... the existing documented 500-on-bad-priority
    path), that connection is left open with an uncommitted transaction until Python's garbage
    collector eventually finalizes it — observed to cause the *next* one-to-two write requests
    to fail with `sqlite3.OperationalError: database is locked`, not the error the client
    actually triggered. Reproduction: `verification/replay/traces/legacy/tickets-create.jsonl`
    was captured with a deliberately-triggered invalid-priority request placed *after* the
    slug-collision test pair during initial harness validation; both subsequent creates failed
    with `database is locked` instead of succeeding — see
    `verification/harness/.run/legacy-tickets-create-boot.log` history (not committed — scratch
    — but reproducible by moving `tickets-create-008-priority-invalid-LAST` earlier in
    `verification/replay/inputs/tickets-create.jsonl` and re-running
    `capture-legacy-goldens.sh`).
  - B: Not worth fixing as a dedicated PB item — a proper connection-per-request pattern (which
    any FastAPI+SQLAlchemy session-scoped dependency gives you essentially for free) makes this
    class of bug structurally impossible in the rewrite regardless of whether it's named. The
    stack migration itself is the fix; no separate REPAIR-tagged behavior needs to exist.
- blocks: nothing (no WO depends on a ruling here; it's informational either way, since
  FastAPI + SQLAlchemy's standard request-scoped session pattern doesn't reproduce this failure
  mode by construction — see modern/CLAUDE.md conventions). Recorded so the executor doesn't
  independently "rediscover" and over-invest in explicitly re-implementing this failure mode as
  a `FIXED` behavior — it should NOT be reproduced; reading B is the practical default even
  without a formal ruling, but this is logged as reading A vs B rather than silently assumed.
- ruling: PENDING (low urgency)
