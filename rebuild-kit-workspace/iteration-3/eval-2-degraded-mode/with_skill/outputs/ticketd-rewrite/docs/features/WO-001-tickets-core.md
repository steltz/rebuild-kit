# docs/features/WO-001-tickets-core.md
id: WO-001            depends_on: []                    milestone: M0
risk: 0.30 (raised from 0.25 post-P9-audit: ASK density now 2 non-blocking pb-proposals
  [OQ-005, OQ-006] instead of 0; inferred-claim ratio still low — all claims cited against
  legacy/app/server.py with a boot-verified trace; no PB entry touches this WO directly;
  complexity moderate [legacy hotspots.md]; legacy test coverage: none exists anywhere in the
  codebase, a floor risk shared by every WO in this backlog, not specific to this one)
usage_weight: none (degraded — see rebuild.json.evidence; ordering falls back to pain/severity
  and "walking skeleton" role per P8 step 4, not measured usage)
pain_weight: 0    context_budget: ~300 lines    gate: false

behaviors:
  - statement: List tickets, optionally filtered by exact `status` match; no pagination, all
      matching rows returned, ordered created_at DESC.
    fidelity: FIXED
    evidence: [legacy/app/server.py:27-37, verification/replay/traces/tickets.legacy.jsonl#tickets-list-empty,
      #tickets-list-filter-status-open]
  - statement: Create a ticket. Requires non-blank `title` (422 `title_required` otherwise, incl.
      whitespace-only). `priority` accepts both enum strings (low/med/high) and legacy numeric
      codes ("1"/"2"/"3"), defaulting to "med"; new tickets always start `status='open'`.
    fidelity: FIXED
    evidence: [legacy/app/server.py:40-55, verification/replay/traces/tickets.legacy.jsonl#tickets-create-happy,
      #tickets-create-priority-numeric-2, #tickets-create-missing-title, #tickets-create-blank-title]
  - statement: Get a single ticket by id. A NONEXISTENT id returns `200 {}`, deliberately NOT a
      404 — the legacy UI depends on it. Do not "fix" this.
    fidelity: FIXED
    evidence: [legacy/app/server.py:58-64, verification/replay/traces/tickets.legacy.jsonl#tickets-get-missing,
      #tickets-get-existing]
  - statement: Slug is derived from title (lowercase, non-alphanumeric runs collapsed to "-",
      truncated to 64 chars) and is NOT guaranteed unique — two distinct titles can collide, and
      nothing in legacy prevents or dedupes this.
    fidelity: FIXED (existing, evidenced, not brief-flagged — do not silently add uniqueness)
    evidence: [legacy/app/util.py:4-6, legacy/db/schema.sql:1-10, verification/replay/traces/tickets.legacy.jsonl#tickets-slug-collision]
  - statement: `created_at` is naive local server time (no timezone offset recorded).
    fidelity: FIXED (not brief-flagged; a candidate PB-proposal, not decided here)
    evidence: [legacy/app/server.py:52]
  - statement: `users` table / `tickets.assignee_id` — schema carried forward structurally; no
      behavior implemented (nothing reads/writes it in legacy).
    fidelity: FREE — outcome: schema shape present for forward-compat. See OQ-004.
    evidence: [legacy/db/schema.sql:12-16, docs/open-questions.md#OQ-004]
  - statement: A non-integer path segment in `GET/POST /api/tickets/<tid>...` (e.g.
      `/api/tickets/abc`) never reaches the handler — Flask's `<int:tid>` route converter
      rejects it first, producing Flask's own default 404 HTML error page. This is a DIFFERENT
      response shape from the "well-formed but nonexistent id" case (claim 3 above, `200 {}`) —
      both are FIXED, but they are not the same behavior and must not be conflated.
    fidelity: FIXED
    evidence: [legacy/app/server.py:58,67 (route pattern), independently confirmed by P9 audit]
  - statement: An out-of-domain `priority` value (anything other than low/med/high/1/2/3) is
      passed through uncaught to the INSERT, violating the DB's CHECK constraint and raising an
      unhandled `sqlite3.IntegrityError` — surfaces as a raw, non-JSON Flask 500.
    fidelity: FIXED (carry forward exactly, crash included) — this is unsanctioned-looking but
      NOT brief-flagged, so it is not a REPAIR target absent a ruling. See
      docs/open-questions.md#OQ-005 (PB-proposal, found by P9 audit, not yet ruled).
    evidence: [legacy/app/server.py:47-53, legacy/db/schema.sql:5, docs/open-questions.md#OQ-005]
  - statement: A non-string `title` (e.g. a JSON number or array) raises an unhandled
      `AttributeError` on `.strip()` — surfaces as a raw, non-JSON Flask 500.
    fidelity: FIXED (carry forward exactly, crash included) — see
      docs/open-questions.md#OQ-006 (PB-proposal, found by P9 audit, not yet ruled).
    evidence: [legacy/app/server.py:43, docs/open-questions.md#OQ-006]

acceptance:
  replay_set: verification/replay/corpus/tickets.requests.jsonl (traces: tickets-list-empty,
    tickets-create-happy, tickets-create-priority-numeric-2, tickets-create-missing-title,
    tickets-create-blank-title, tickets-get-missing, tickets-get-existing,
    tickets-list-filter-status-open, tickets-slug-collision — 9 of the 12 tickets traces; the
    other 3 (tickets-close-*) belong to WO-002)
  tests: verification/characterization/test_tickets.py (test_create_requires_title,
    test_create_blank_title_rejected, test_create_defaults_priority_med,
    test_create_numeric_priority_mapping, test_get_missing_returns_200_empty_object,
    test_list_no_pagination_returns_all, test_list_filter_by_status,
    test_slug_collision_not_prevented)
  NOT YET COVERED: the two P9-audit crash-path behaviors (non-integer tid 404, invalid-priority
    500, non-string-title 500) have no replay-corpus traces or characterization tests yet —
    add them once OQ-005/OQ-006 are ruled (the correct assertion depends on the ruling: either
    "still crashes the same way" or "now returns a JSON validation error").
escalation: consult legacy/app/server.py:27-64 and legacy/app/util.py only if spec ambiguity
  found; do not bulk-read legacy/.

## Why this is Milestone 0 (walking skeleton)

Per P8 procedure: M0 needs one thin end-to-end slice — entry, one core action, persistence,
response — with no cross-WO dependencies, to validate the FastAPI+Postgres stack choice and
prove the twin-boot harness plumbing before forty WOs depend on it being right. Tickets
list/create/get has zero dependency on the notification infrastructure (WO-004) or the reset
flow (WO-003), making it the cleanest walking skeleton. Close-ticket is deliberately split into
WO-002 because it depends on WO-004 (async dispatch) — bundling it into M0 would mean M0 either
re-introduces PB-001 (unacceptable — the rewrite was commissioned partly to fix it) or silently
grows M0's dependency surface.
