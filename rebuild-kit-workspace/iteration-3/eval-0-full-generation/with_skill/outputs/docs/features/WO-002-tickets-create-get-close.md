id: WO-002            depends_on: [WO-000, WO-001]       milestone: M1
risk: 0.45 (PB-003/PB-007/PB-010/OQ-008 all touch this WO's area, but every non-trivial claim is
  now traced (P7), not inferred -- lowers the inferred-claim ratio substantially vs. a typical
  first draft; PB-011/OQ-011 (P9 audit findings) add 4 untraced-but-verified behaviors, see below)
usage_weight: 0.303 (create 21.15% + get-by-id 9.2% -- close's 4.95% is WO-001's dependency, not
  counted twice)   pain_weight: 0.3 (PB-003 support pain)   context_budget: ~350 lines   gate: false

**Blocked by OQ-011** (`docs/open-questions.md#OQ-011`): do not mark this WO `done` in the ledger
until the 4 behaviors under "P9 audit findings (PB-011)" below have real traces captured (not just
source-verified) under `verification/replay/traces/`.

## Reading list

- `docs/features/draft/tickets-crud.md` — full (this WO's primary source).
- `docs/domain/tickets.md` — full.
- `docs/contracts/openapi.yaml` paths `/api/tickets` POST, `/api/tickets/{id}` GET,
  `/api/tickets/{id}/close` POST + their linked schemas in `docs/contracts/schemas/`.
- `verification/replay/traces/tickets-crud.jsonl` (all traces except the 3 list-only ones WO-000
  already covers) and `verification/replay/traces/tickets-close.jsonl` (all 3).
- `docs/open-questions.md#OQ-001` and `#OQ-008` (both affect this WO's scope — read the current
  "ruling" field; OQ-008 is already resolved by trace evidence, OQ-001 does not block this WO's
  close, see its entry for why).

## Behaviors

### POST /api/tickets (create)

- statement: `title` required, non-empty after `.strip()`; empty/whitespace-only/missing all
    return `422 {"error": "title_required"}`.
  fidelity: FIXED. evidence: [ticketd/app/server.py:42-45, traces: tickets-create-empty-title-003,
    tickets-create-no-body-004]
- statement: explicit JSON `{"title": null}` is an unhandled `500` (HTML error page), NOT the 422
    path.
  fidelity: FIXED (preserve exactly, including the non-JSON HTML body -- this is deliberately
    faithful reproduction of a legacy bug, not an oversight; see OQ-008's resolution).
  evidence: [ticketd/app/server.py:43, trace: tickets-create-null-title-900 -- **traced**, real
    execution, `verification/replay/traces/tickets-crud.jsonl`]
- statement: `priority` accepts `"1"`/`"2"`/`"3"` (mapped to low/med/high), any other string
    passed through as-is (including invalid values), or defaults to `"med"` if absent.
  fidelity: FIXED. evidence: [ticketd/app/server.py:47-49, trace: tickets-create-001]
- statement: a `priority` value outside `{low,med,high}` is not app-validated and results in an
    unhandled `500` when it violates the target DB's CHECK constraint.
  fidelity: FIXED (preserve; see `docs/domain/tickets.md`'s invariant note for the "hardening"
    option this brief does not currently authorize).
  evidence: [ticketd/app/server.py:47-49, trace: tickets-create-invalid-priority-906 -- traced,
    captured in isolation to avoid the PB-004 connection-lock confound]
- statement: `slug` is derived via `slugify(title)` (lowercase, `[^a-z0-9]+` -> `-`, trim, ≤64
    chars) with **no uniqueness check** — two titles that normalize to the same slug both succeed
    and both get that slug.
  fidelity: FIXED — implement this baseline (matching current, collision-permitting behavior)
    faithfully. Per OQ-001's current entry, this does NOT block this WO's close: preserving
    observed behavior needs no ruling. If/when OQ-001 is ruled to change this, that is separately
    scoped follow-up work, not a reason to hold this WO open.
  evidence: [ticketd/app/util.py:4-6, ticketd/app/server.py:50-55, trace:
    tickets-create-slug-collision-002]
- statement: response `201 {"id": <int>, "slug": <string>}` on success.
  fidelity: FIXED. evidence: [ticketd/app/server.py:55, trace: tickets-create-001]

### GET /api/tickets/{id} (get)

- statement: missing ticket -> `200 {}` (empty object), **not** `404`.
  fidelity: FIXED — required by PB-006 (no UI changes). Do not "fix" this without a human ruling
    (`docs/open-questions.md#OQ-004`, currently declined-for-now).
  evidence: [ticketd/app/server.py:58-64, trace: tickets-get-missing-008]
- statement: found ticket -> `200` with full ticket object (`docs/contracts/schemas/ticket.json`).
  fidelity: FIXED. evidence: [ticketd/app/server.py:64, trace: tickets-get-found-007]
- statement: non-numeric id in the path -> `404` (framework-level routing, not app logic).
  fidelity: FIXED as an outcome (a non-numeric id is rejected); FREE on mechanism (however the
    target framework's path-typing rejects it).
  evidence: [ticketd/app/server.py:58, trace: tickets-get-non-numeric-id-009]

### POST /api/tickets/{id}/close (close)

- statement: real open->closed transition -> `200 {"closed": true}`, `status` set to `closed`,
    `closed_at` stamped, and a notification is dispatched (per WO-001's decoupled mechanism, NOT
    synchronously — see ED-001).
  fidelity: FIXED for the DB transition + response shape; REPAIR (owned by WO-001, this WO just
    calls WO-001's dispatch function) for dispatch timing.
  evidence: [ticketd/app/server.py:68-77, trace: close-first-transition-001]
- statement: already-closed ticket OR nonexistent id -> both return `200 {"closed": false}`,
    indistinguishable from each other, no notification sent.
  fidelity: FIXED. evidence: [ticketd/app/server.py:69-71, traces: close-idempotent-noop-002,
    close-nonexistent-id-003 — byte-identical response bodies, verified in
    verification/characterization/test_tickets_close.py]
- statement: notification recipient is always the fixed address `watchers@example.internal`,
    never per-ticket, never derived from `assignee_id` (which is never populated — see
    `docs/domain/users.md`).
  fidelity: FIXED. evidence: [ticketd/app/server.py:76]

### P9 audit findings (PB-011) — verified but NOT YET traced, see OQ-011

- statement: a non-object JSON body to `POST /api/tickets` (e.g. JSON `[]`, `"hello"`, `42` —
    anything that survives `get_json(silent=True) or {}`'s truthiness check without being a dict)
    causes `body.get(...)` to raise `AttributeError` -> unhandled 500. Same family as the already-
    traced `{"title": null}` case (OQ-008) but a distinct trigger.
  fidelity: FIXED (preserve — verified against source, not yet captured as a trace).
  evidence: [ticketd/app/server.py:42-43, independently verified by direct code reading during P9
    audit, 2026-08-09 — NOT YET traced, see OQ-011]
- statement: explicit `{"priority": null}` (key present, value JSON `null`) bypasses the `"med"`
    default (which only applies when the key is *absent*), becomes the literal string `"None"` via
    `str(None)`, is passed through unchanged, and violates the DB CHECK constraint -> unhandled
    500. Distinct trigger from the already-traced `tickets-create-invalid-priority-906` (arbitrary
    bad string), same outcome.
  fidelity: FIXED (preserve — verified against source, not yet captured as a trace).
  evidence: [ticketd/app/server.py:47, independently verified during P9 audit — NOT YET traced,
    see OQ-011]
- statement: `GET /api/tickets?status=` (empty string, e.g. bare `?status` with no value) does
    **not** behave like "any other invalid value returns an empty array" — `if status:` treats
    empty string as falsy, so no filter is applied and the FULL unfiltered list returns instead.
    **This corrects WO-000's list-filter behavior claim, which was too broad** (WO-000 said "any
    other value... returns an empty array" — that's true for non-empty junk like `"bogus"` but
    false for the empty string specifically).
  fidelity: FIXED (preserve — verified against source, not yet captured as a trace). If you are
    implementing WO-000 before this correction lands there too, apply this same correction to
    WO-000's list-filter behavior.
  evidence: [ticketd/app/server.py:29,32-34, independently verified during P9 audit — NOT YET
    traced, see OQ-011]
- statement: `POST /api/tickets/<id>/close` with a non-numeric `<id>` (e.g. `.../abc/close`) has
    never been verified end-to-end for this specific route (only `GET /api/tickets/<id>` was
    traced, `tickets-get-non-numeric-id-009`) — presumed identical (Flask `<int:tid>` converter,
    framework-level 404) by analogy, but NOT confirmed.
  fidelity: FIXED as an outcome (presumed, pending verification) — **run this before closing the
    WO**, don't just assume the analogy holds.
  evidence: [none yet — this is a verification gap, not a verified claim, see OQ-011]

## Acceptance

- L1: `docs/contracts/openapi.yaml` — `POST /api/tickets`, `GET /api/tickets/{id}`,
  `POST /api/tickets/{id}/close` operations validate against live responses, including the 422/500
  error shapes (note the 500 path has NO defined schema — do not invent one, the contract
  correctly leaves it undefined since legacy's shape there is an HTML page, not JSON).
- L2: live-modern equivalents of `test_tickets_crud.py`'s non-list tests and all of
  `test_tickets_close.py`.
- L3: `verification/harness/diff-run.sh tickets-crud` (all 13 traces except the 3 WO-000 owns) and
  `diff-run.sh tickets-close` (all 3) must pass.
- gate: false — but note `tickets-crud-lock-cascade-901`'s trace documents a legacy defect
  (PB-004) this WO's target stack should structurally not reproduce (Postgres + proper
  connection/session lifecycle vs. SQLite's leaked-connection lock). No explicit acceptance check
  forces this — it falls out of using the target stack correctly — but if a reviewer notices the
  new stack ALSO leaks connections, that is a WO-000/architecture-level regression worth raising
  as its own finding, not something this WO's replay set will catch on its own (the replay set
  doesn't stress concurrent/interleaved requests the way a real production incident would).

## Escalation

Consult `ticketd/app/server.py:40-77` (create + get + close handlers) and `ticketd/app/util.py`
(whole file, 7 lines) only if the draft spec/traces leave something ambiguous. Do not read the
auth/reset handlers (`server.py:80-108`) — that's WO-004's scope.
