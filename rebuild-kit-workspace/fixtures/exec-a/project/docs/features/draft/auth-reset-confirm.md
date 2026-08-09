# Draft spec: POST /api/auth/reset/confirm

usage_weight: 0.01 · perf envelope (low-confidence): p50 119ms / p95 301ms / p99 305ms —
notably this route has no SMTP call at all, yet shows a similar elevated latency profile to
the SMTP-calling routes in the sampled log. Flagged as a discrepancy worth noting rather than
silently explained away: either (a) the log's per-route timings are synthetic/not causally
generated from the real code paths (consistent with the log's already-established
1-hour-synthetic-window issue), or (b) some other per-request cost exists on this path that
isn't yet accounted for. Not enough evidence to conclude either way — do not treat this
route's perf envelope as a reliable NFR floor.

## Behaviors

- statement: Looks up `reset_tokens` by exact `token` match. If no row matches, **or** if
    `time.time() - created_ts > 1800` (30 minutes), respond `403 {"error": "invalid_token"}` —
    the identical body and status for both "wrong token" and "expired token."
  fidelity: FIXED — explicitly a deliberate non-disclosure design per the code comment; must
    be preserved exactly through WO-003's token-mechanism REPAIR.
  evidence: [legacy/app/server.py:99-105, comment at line 104]
  confidence: cited

- statement: On success, the token row is deleted (single-use) and the response is
    `200 {"ok": true, "email": <the row's email>}`.
  fidelity: FIXED
  evidence: [legacy/app/server.py:106-108]
  confidence: cited

- statement: Deletion happens before the response is constructed but the row's `email` value is
    read into `row` before the DELETE — no risk of losing the value, but note the DELETE is
    keyed on `token`, not `id` (there is no `id` column on this table at all, see
    docs/domain/reset_token.md) — WO-003's redesigned table needs an explicit single-use
    guarantee even once a real PK exists.
  fidelity: FIXED (current mechanism) — mechanism itself (delete-by-token vs. delete-by-id or
    mark-consumed) is FREE once WO-003 introduces a proper key.
  evidence: [legacy/app/server.py:101-108]
  confidence: cited

- statement: No rate limiting exists on this route (unlike the request route) — an attacker can
    attempt unlimited token guesses within the 30-minute window with no throttling.
  fidelity: ASK — this looks like a real gap, but it is not named in the brief (PB-002 is about
    token *strength*, not about confirm-endpoint throttling) and "guessing" an MD5-of-known-ish-
    inputs today is a different threat model than guessing a CSPRNG token post-WO-003 (where
    brute-forcing becomes computationally infeasible regardless of rate limiting). Filed as a
    PB proposal — see `docs/open-questions.md` OQ-009.
  evidence: [legacy/app/server.py:98-108] (absence of any rate-limit code on this route)
  confidence: inferred

- statement: **Added after P9 audit — previously uncovered branch.** Non-dict JSON body (bare
    list/string/number/bool) is not caught by `request.get_json(silent=True) or {}` and reaches
    `body.get("token", "")`, raising `AttributeError` on a non-dict → uncaught 500. Same pattern
    as `create_ticket`/`request_reset` — see docs/features/draft/tickets-create.md.
  fidelity: FIXED (as-coded gap; not brief-mentioned)
  evidence: [legacy/app/server.py:100-102]
  confidence: traced (P9 audit finding)

- statement: **Concurrency note, raised during P9 audit, UNVERIFIABLE from source alone.**
    Whether two simultaneous confirm requests for the SAME token could both pass the
    `row is None or expired` check before either DELETE executes (both succeeding, double-
    spending a single-use token) depends on SQLite's actual locking behavior under Flask's
    dev-server threading model, which is not something static reading of `server.py:98-108`
    settles by itself. Not claimed as a confirmed bug; flagged so WO-003's redesigned table
    (with a real PK) considers using an atomic `DELETE ... RETURNING` or equivalent
    check-and-consume rather than separate SELECT-then-DELETE statements, since the FIXED
    single-use *outcome* (not the current two-statement mechanism) is what must be preserved.
  fidelity: FREE (mechanism) — outcome (true single-use even under concurrent requests) is a
    reasonable strengthening for WO-003 to adopt, not a brief-mandated REPAIR.
  evidence: [legacy/app/server.py:98-108] (inferred limitation of the current two-statement
    mechanism, not a demonstrated race)
  confidence: inferred

## Acceptance
  replay_set: auth-reset-confirm-*.jsonl (valid token, unknown token, expired token, replay of
    an already-consumed token) — captured T2 golden. **Not yet extended** to cover the non-dict
    body case (P9 finding above); add before WO-008 closes. The concurrency note above is not
    replay-testable via this harness's sequential driver and would need a dedicated concurrent-
    request test if WO-003 wants to assert it explicitly.
  tests: characterization/auth/reset-confirm.spec
