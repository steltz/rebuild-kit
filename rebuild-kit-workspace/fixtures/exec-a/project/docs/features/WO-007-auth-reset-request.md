id: WO-007            depends_on: [WO-002, WO-003]         milestone: M1
risk: 0.55 (PB severity high via PB-001/PB-002 both landing here; ASK density: OQ-006 (bypass
  header) touches this route but does not block it -- preserve as-is; complexity medium)
usage_weight: 0.0195
pain_weight: 0.9 (both PB-001 and PB-002 have a call site here)
context_budget: ~350 lines (this WO + WO-002 + WO-003 + docs/features/draft/auth-reset-request.md)
gate: false (its dependencies WO-002/WO-003 already carry the gates; this WO is integration)

## What this WO does
Wire `POST /api/auth/reset` to WO-003's token mechanism and WO-002's async dispatch.

behaviors:
  - statement: "Rate limit: 3 requests/hour per email, checked via count of existing tokens
      issued to that email in the last 3600 seconds; if X-Internal-Bypass: 1 header is present,
      skip the check entirely."
    fidelity: FIXED (including the bypass header — preserve its existence and effect exactly;
      OQ-006 is about whether it SHOULD exist, not a license to alter it unilaterally while
      unruled)
    evidence: [legacy/app/server.py:84-89, docs/open-questions.md OQ-006]
  - statement: "Response is always 200 {ok: true} regardless of whether email matches a real
      user (enumeration-resistant) -- must survive both WO-002 and WO-003's REPAIRs unchanged."
    fidelity: FIXED
    evidence: [legacy/app/server.py:95]
  - statement: "email is read with no format validation; any string accepted. Interacts with
      WO-002's async dispatch: once mail delivery is out-of-band, a malformed address can no
      longer surface as a request-time failure the way it might today (uncaught SMTP-layer
      exception under PB-001's synchronous call). Decide and document how a malformed address
      behaves now (silently accepted and fails downstream, vs. request-time validation added)."
    fidelity: ASK (implementation question for this WO specifically, not a new PB — see
      docs/features/draft/auth-reset-request.md's note on this exact interaction)
    evidence: [legacy/app/server.py:82-83]

acceptance:
  replay_set: auth-reset-request-*.jsonl (6 traces, captured T2 golden, self-check validated;
    token-bearing fields already normalized per diff-rules.yaml)
  tests: verification/characterization/test_against_golden.py
  l1: docs/contracts/openapi.yaml /api/auth/reset
  l3: verification/harness/diff-run.sh auth-reset-request

escalation: legacy/app/server.py:80-96 only.
