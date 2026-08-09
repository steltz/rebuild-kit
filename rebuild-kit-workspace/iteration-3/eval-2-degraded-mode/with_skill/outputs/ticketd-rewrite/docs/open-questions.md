# Open Questions — ASK register & PB proposals

<!-- Executor + generator both append here. Never delete entries; rulings are appended.
     Each new OQ gets a ruling brief generated into guide/briefs/ (templates/ruling-brief.md). -->

## OQ-001 — Does `X-Internal-Bypass: 1` on `/api/auth/reset` need to survive the rewrite?
- raised_by: generator P4
- kind: ambiguity
- readings:
  - A: It's a deliberate internal-tooling escape hatch (e.g. for support staff or automated
    tests) to skip the per-email rate limit — keep it, but move it behind an explicit
    authenticated/internal-only mechanism instead of an unauthenticated header anyone can send.
    evidence: legacy/app/server.py:84 (`if request.headers.get("X-Internal-Bypass") != "1"`),
    no authentication check guards this branch.
  - B: It's leftover debug/test scaffolding that should not exist in a security-sensitive
    rate-limit path and should be dropped entirely. evidence: same citation; comment marks it
    "undocumented bypass header" (legacy/app/server.py:84), no caller or doc references it
    anywhere else in the tree.
- blocks: [WO-003]   (rate-limit behavior in the rewritten reset flow)
- ruling: PENDING

## OQ-002 — What delivery guarantee does the async email dispatch need (PB-001 fix)?
- raised_by: generator P4
- kind: inferred-only
- readings:
  - A: At-least-once via a durable outbox table + worker (survives process restarts, can
    retry on SMTP failure); needed if watchers/reset-token delivery is considered
    business-critical. evidence: legacy/app/server.py:75-76 comment implies outage-sensitivity
    was already a known pain, but no data exists on how often SMTP actually fails in production
    (no APM — see problem-brief.md OQ-INTAKE-02).
  - B: Best-effort via an in-process background task queue (e.g. FastAPI `BackgroundTasks` or a
    lightweight task queue), accepting at-most-once with no retry, since the legacy system had
    no retry logic either (a synchronous, un-retried `send_mail` call) and REPAIR only commits
    to removing the blocking behavior, not adding new reliability guarantees beyond what PB-001
    asked for.
- blocks: [WO-004]
- ruling: PENDING

## OQ-003 — Does anything still call `/internal/export/csv` or import `legacy_import.py`?
- raised_by: generator P1/P4
- kind: discrepancy
- readings:
  - A: Both are dead — the CSV export route's own comment says "written for the 2020 audit; no
    caller since" (legacy/app/server.py:112), and `legacy_import.py`'s docstring says "Nothing
    imports this module" (legacy/app/legacy_import.py:1). Candidates for `do-not-port.md`.
  - B: An out-of-band consumer exists that the code comments don't know about (e.g. a cron job,
    an external audit script) — cannot be ruled out without access logs, which are unavailable
    this run (problem-brief.md OQ-INTAKE-02).
- blocks: []   (flags gate review only; provisionally staged as do-not-port, see docs/do-not-port.md)
- ruling: PENDING

## OQ-004 — Is the `users` table / `tickets.assignee_id` a dead/unfinished feature or missing routes?
- raised_by: generator P1/P3
- kind: discrepancy
- readings:
  - A: Assignment was planned but never shipped in this codebase — no route reads or writes
    `users` or `assignee_id` anywhere in `app/server.py`. Port the schema shape (FREE on
    mechanism) but treat assignment as out of scope for M0/M1 since no behavior exists to
    characterize.
  - B: An assignment feature exists elsewhere (a second service, an admin script not in this
    tree) that this handover didn't include. Cannot be ruled out — no history, no other source
    tree was provided.
- blocks: []   (flags gate review only; ticket/user domain model in docs/domain/ notes both
  tables but WOs only cover observed routes)
- ruling: PENDING

## OQ-005 — Should an out-of-domain `priority` value crash with a raw 500? (P9 finding, PB-proposal)
- raised_by: audit P9 (independent fresh-context falsification pass)
- kind: pb-proposal
- readings:
  - A: This is unsanctioned, unintended behavior — nothing in the problem brief flags it, and a
    raw non-JSON 500 (Flask's default error page) on a client sending e.g.
    `{"priority": "urgent"}` is a poor API experience for any consumer expecting JSON errors like
    every other validation failure in this app (`422 title_required`, `429 rate_limited`,
    `403 invalid_token`). Candidate for promotion to a PB entry with disposition REPAIR
    (add the same kind of validation the other fields get) if a human agrees.
  - B: No user ever reported this as a problem (it's not in the handover notes), and the
    contractor may have accepted "trust the client" as a deliberate tradeoff for an internal
    tool. Without testimony, this could just as easily be out-of-scope.
- detail: `create_ticket` (legacy/app/server.py:47-53) only remaps `"1"/"2"/"3"`; any other
  string is passed through uncaught to an INSERT that violates the DB's
  `CHECK (priority IN ('low','med','high'))` (legacy/db/schema.sql:5), raising an unhandled
  `sqlite3.IntegrityError` that surfaces as a raw 500. Confirmed via independent audit, not yet
  reproduced against a live instance.
- blocks: []   (flags gate review only; WO-001 carries this forward as FIXED — i.e.
  unimplemented validation, matching legacy exactly — pending this ruling)
- ruling: PENDING

## OQ-006 — Should a non-string `title` crash with a raw 500? (P9 finding, PB-proposal)
- raised_by: audit P9 (independent fresh-context falsification pass)
- kind: pb-proposal
- readings:
  - A: Same reasoning as OQ-005 — unsanctioned, arguably a defect, candidate REPAIR (validate
    JSON types before calling `.strip()`).
  - B: Same counter-reasoning as OQ-005 — no testimony, could be an accepted tradeoff.
- detail: `body.get("title", "").strip()` (legacy/app/server.py:43) assumes a string; a JSON
  body with `"title": 123` or `"title": [1, 2]` raises an unhandled `AttributeError` (int/list
  has no `.strip`), surfacing as a raw 500. Confirmed via independent audit, not yet reproduced
  against a live instance.
- blocks: []   (flags gate review only; WO-001 carries this forward as FIXED pending this ruling)
- ruling: PENDING
