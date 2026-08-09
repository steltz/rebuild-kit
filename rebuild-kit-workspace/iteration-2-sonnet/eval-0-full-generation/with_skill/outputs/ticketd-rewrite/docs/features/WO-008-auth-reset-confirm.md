id: WO-008            depends_on: [WO-003]                 milestone: M1
risk: 0.4 (PB-002 touches this via the token mechanism, already absorbed by WO-003; complexity
  low; the one real ASK here (OQ-009, confirm-endpoint rate limiting) doesn't block closing)
usage_weight: 0.01
pain_weight: 0.3
context_budget: ~250 lines (this WO + WO-003 + docs/features/draft/auth-reset-confirm.md)
gate: false

## What this WO does
Wire `POST /api/auth/reset/confirm` to WO-003's token mechanism.

behaviors:
  - statement: "Looks up by token; no row OR expired (>30min) -> 403 {error: invalid_token},
      IDENTICAL body/status for both causes (deliberate non-disclosure). On success: token
      consumed (single-use) and 200 {ok: true, email: <row's email>}."
    fidelity: FIXED — must survive WO-003's mechanism REPAIR unchanged.
    evidence: [legacy/app/server.py:98-108, docs/domain/reset_token.md]
  - statement: "No rate limiting on this endpoint today (unlike request)."
    fidelity: ASK — OQ-009 (PB proposal), does not block this WO's close; do not add
      speculatively.
    evidence: [docs/open-questions.md OQ-009]

acceptance:
  replay_set: auth-reset-confirm-*.jsonl (5 traces, captured T2 golden including the full
    request->capture-token->confirm chain and a replay-of-consumed-token case, self-check
    validated; request.body.token normalized per diff-rules.yaml)
  tests: verification/characterization/test_against_golden.py
  l1: docs/contracts/openapi.yaml /api/auth/reset/confirm
  l3: verification/harness/diff-run.sh auth-reset-confirm

escalation: legacy/app/server.py:98-108 only.
