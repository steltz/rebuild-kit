# Open Questions — ASK register & PB proposals

<!-- Executor + generator both append here. Never delete entries; rulings are appended.
     Each new OQ gets a ruling brief generated into guide/briefs/ (templates/ruling-brief.md). -->

## OQ-001 — Should `created_at`/`closed_at` move from naive local time to timezone-aware UTC?

- raised_by: generator P3/P4 (code-observed, not human-reported)
- kind: pb-proposal
- readings:
  - A: naive local time is a latent bug (server-locale-dependent, ambiguous across DST
    transitions, breaks any cross-timezone comparison) — evidence: `legacy/app/server.py:52`,
    the code's own inline comment `# naive local time!` suggests even the original author flagged
    it as suspect.
  - B: nothing in the handover notes names this as a problem; some downstream consumer might
    already assume server-local time and a silent switch to UTC would shift displayed times —
    evidence: no consumer code exists in this repo either way (no read of these fields performs
    timezone math), so reading B is unfalsifiable from source alone, not actively supported.
- blocks: [WO-002] (ticket read/write behaviors — this decision changes stored value shape)
- ruling: PENDING
  <!-- becomes: <decision> — ruled_by <who>, <date>; propagated via spec-patch <commit> -->

## OQ-002 — reserved / not used

Folded into WO-004 as a FREE choice (email-dispatch mechanism) during drafting, not an ASK —
outcome ("must not block the response") is REPAIR-mandated by PB-001; the mechanism itself needs
no human ruling. Left as a gap rather than renumbering downstream entries.

## OQ-003 — Is the `users` table / `tickets.assignee_id` dead, or maintained outside this repo?

- raised_by: generator P3 domain recon
- kind: ambiguity
- readings:
  - A: vestigial scaffolding — no route in `legacy/app/server.py` ever touches `users` or
    `assignee_id`; safe to carry forward as an unused stub. Evidence: full read of `server.py`,
    zero references.
  - B: populated/consumed by something outside this handover (admin script, BI job, manual SQL)
    — evidence: none available (no logs, no prod DB access this run); can't be ruled out from
    source alone.
- blocks: [] (no WO in this backlog touches `users` directly) — flags gate review for the future
  migration WO once DB access exists and a real row count is known.
- ruling: PENDING

## OQ-004 — Is the absence of any auth/session layer on the Tickets API intentional?

- raised_by: generator P3 domain recon
- kind: ambiguity
- readings:
  - A: intentional — this is described as an "internal ticket tracker," plausibly sitting behind
    a network perimeter (VPN, internal LB) that provides access control outside the app itself.
    No evidence either way was supplied.
  - B: a gap — the password-reset flow exists (implying *some* notion of user identity/auth
    matters) but nothing gates `POST /api/tickets`, `POST /api/tickets/<id>/close`, or the CSV
    export behind any credential check at all. Evidence: full read of `server.py`, no
    `@login_required`-equivalent anywhere, no session/cookie/token check on any ticket route.
- blocks: [] — flags gate review only; no WO in this backlog adds auth (none was requested), but
  the FastAPI rewrite should not accidentally *add* auth either, since that would be an
  unsanctioned behavior change in the other direction.
- ruling: PENDING

## OQ-005 — Should ticket slug collisions be prevented? (PB-proposal)

- raised_by: generator P4 behavioral extraction
- kind: pb-proposal
- readings:
  - A: bug — `util.py:5`'s own comment names the exact collision case ("Fix DB" / "fix db!" ->
    same slug); no uniqueness constraint exists in the DDL or in code. Evidence:
    `legacy/app/util.py:4-6`, `legacy/db/schema.sql:1-10`.
  - B: harmless — nothing in this repo looks a ticket up by slug (only by `id`), so a collision
    has no observed functional consequence today. Evidence: no route pattern matches on `slug`.
- blocks: [] — flags gate review; not blocking because reading B is well-supported by the actual
  code (slug is write-only / display-only in this codebase as far as it's visible here).
- ruling: PENDING

## OQ-006 — Should expired/unconfirmed `reset_tokens` rows be cleaned up? (PB-proposal)

- raised_by: generator P4 behavioral extraction
- kind: pb-proposal
- readings:
  - A: yes — the table has no primary key, no cleanup job, and no code path deletes a row except
    a successful confirm (`legacy/app/server.py:106`); rows from abandoned/expired reset attempts
    accumulate forever. Evidence: full read of `server.py`'s two reset routes, `db/schema.sql:18-22`.
  - B: no evidence this has ever caused a problem (no runtime/ops evidence available this run) —
    could be inconsequential at ticketd's actual data volume, which is unknown.
- blocks: [] — flags gate review for the migration WO (a natural place to add either a TTL index
  in Postgres or a periodic purge, if ruled in).
- ruling: PENDING

## OQ-007 — Keep, document, or drop the `X-Internal-Bypass` reset-rate-limit bypass header?

- raised_by: generator P4 behavioral extraction
- kind: ambiguity
- readings:
  - A: keep as-is (FIXED) — it's real, evidenced code (`legacy/app/server.py:84`) that some
    internal caller may depend on today; removing it silently could break that caller.
  - B: it's an undocumented backdoor around abuse protection with no comment, docstring, test, or
    PB entry explaining its intended caller or scope — carrying it forward into a fresh Postgres/
    FastAPI build without deliberate sign-off is exactly the "faithfully rebuild the cruft" risk
    the fidelity taxonomy exists to catch.
- blocks: [] — flags gate review for WO-003 (auth/reset). Not blocking WO-003's other behaviors
  (token generation, expiry, non-disclosure) because those are independently evidenced and
  unambiguous.
- ruling: PENDING

## OQ-008 — What should the error contract be for an invalid `priority` value on ticket create?

- raised_by: generator P4 behavioral extraction (referenced inline in
  docs/features/draft/tickets-list-create-get.md at draft time; NOT actually filed here until the
  P9 audit caught the dangling reference — audit/report.md finding I-1)
- kind: inferred-only
- readings:
  - A: today's behavior (untested/accidental) is an unhandled `sqlite3.IntegrityError` from the
    CHECK constraint violation, surfacing as a bare Flask 500 with no JSON error body — evidence:
    `legacy/app/server.py:46-49` (coercion logic), `legacy/db/schema.sql:5` (the CHECK), and the
    absence of any try/except around the INSERT at `server.py:50-54`.
  - B: this is plainly a bug (a validation input should never reach a raw 500), and the rewrite
    should return a proper `422 {"error": "invalid_priority"}` instead — no PB entry sanctions
    this reading, so it stays a proposal, not a plan.
- blocks: [] — flags gate review for WO-002. WO-002's acceptance notes a characterization test
  for today's (ugly) 500 behavior as the safe default pending this ruling.
- ruling: PENDING

## OQ-009 — Malformed-body crash paths on ticket create: non-string `title`, explicit-null `priority`

- raised_by: P9 adversarial audit (audit/report.md findings C-1, C-2 — coverage gaps: real
  branches with no prior spec statement)
- kind: discrepancy
- readings:
  - A: same disposition as OQ-008 — these are two more ways to reach an unhandled 500 (a
    non-string `title`, e.g. `{"title": 5}` or `{"title": null}`, raises `AttributeError` at the
    `.strip()` call, `legacy/app/server.py:43`; an explicit `{"priority": null}` becomes the
    string `"None"` via `str(None)` at `server.py:47` and falls into the same untested
    CHECK-violation path as OQ-008). Port as-is (FIXED, ugly-but-real) pending a ruling, same as
    OQ-008.
  - B: a rewrite in a stricter framework (FastAPI + Pydantic) will likely reject a non-string
    `title` or a null `priority` at the request-validation layer automatically, BEFORE reaching
    application code at all — meaning "porting the 500" may not even be achievable without
    deliberately bypassing Pydantic's type coercion. If so, this becomes a REPAIR-by-necessity
    (validation-layer 422 instead of handler-level 500) rather than a free choice, which is worth
    surfacing to a human rather than treating as inconsequential.
- blocks: [] — flags gate review for WO-002, alongside OQ-008 (same handler, same error-shape
  question, worth ruling together).
- ruling: PENDING
