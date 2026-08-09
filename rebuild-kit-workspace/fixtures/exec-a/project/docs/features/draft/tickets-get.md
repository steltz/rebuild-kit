# Draft spec: GET /api/tickets/<id> (fetch one)

usage_weight: 0.092

## Behaviors

- statement: Existing ticket id → `200`, full ticket object.
  fidelity: FIXED
  evidence: [legacy/app/server.py:58-64]
  confidence: cited

- statement: Nonexistent ticket id → `200 {}` (empty JSON object), **not** `404`. Explicitly
    called out in a code comment as a historical quirk the legacy UI depends on.
  fidelity: FIXED — this is precisely the kind of behavior PB-005 (no UI changes) freezes.
    Returning a conventional 404 here, however "more correct," would be unsanctioned scope
    creep against an explicit non-goal.
  evidence: [legacy/app/server.py:59-63, comment at line 62]
  confidence: cited

- statement: Non-integer `<id>` in the path (e.g. `/api/tickets/abc`) — Flask's `<int:tid>`
    converter rejects the route match entirely before the view function runs, producing
    Flask's standard `404 Not Found` HTML error page (not this route's JSON `{}` behavior).
  fidelity: FIXED (framework-level behavior, not app logic — but still an observable contract
    detail worth stating so the FastAPI path-param type doesn't silently diverge, e.g. by
    returning a JSON 422 instead of matching Flask's plain 404)
  evidence: [legacy/app/server.py:58] (Flask `<int:tid>` converter semantics — inferred from
    Flask's documented routing behavior, not from a line of ticketd's own code)
  confidence: inferred
  note: worth a characterization test explicitly, since it's easy to get "close enough" wrong
    here (FastAPI's default path validation returns a structured JSON 422, which would be an
    observable divergence).

## Acceptance
  replay_set: tickets-get-*.jsonl (existing id, nonexistent id, non-integer id)
  tests: characterization/tickets/get.spec
