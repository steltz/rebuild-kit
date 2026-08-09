# docs/features/WO-003-auth-reset.md
id: WO-003            depends_on: [WO-004]               milestone: M1
risk: 0.68 (inferred-claim ratio low [all cited, boot-verified]; ASK density high — OQ-001
  directly blocks this WO; PB severity high [PB-002] touches this WO's core; complexity
  moderate-high [rate limiting + expiry + non-disclosure semantics]; zero legacy test coverage;
  expected-divergence entries unratified — several factors independently push this well above
  the 0.5 gate threshold)
usage_weight: none (degraded)   pain_weight: 1.0 (PB-001 + PB-002 both touch this WO)
context_budget: ~350 lines    gate: true
blocked_by_asks: [OQ-001]

behaviors:
  - statement: Rate-limit reset requests to 3/hour per email (rolling window); over-limit
    returns 429 rate_limited.
    fidelity: FIXED
    evidence: [legacy/app/server.py:16-17,84-89, verification/replay/traces/auth-reset.legacy.jsonl#reset-request-rate-limited]
  - statement: The `X-Internal-Bypass: 1` header, unauthenticated, skips the rate limit.
    fidelity: ASK — docs/open-questions.md#OQ-001. DO NOT implement either reading (keep-with-
    proper-auth vs. drop-entirely) until ruled. This WO cannot close until OQ-001 is ruled.
    evidence: [legacy/app/server.py:84, verification/replay/traces/auth-reset.legacy.jsonl#reset-request-bypass-header]
  - statement: Token generation uses a CSPRNG (not MD5-of-guessable-input). Externally observable
    outcome (opaque single-use token, 30-min validity, non-disclosure on failure) is FIXED; the
    generation mechanism changes.
    fidelity: REPAIR — PB-002.
    evidence: [legacy/app/server.py:90]   divergence: none declared in
    verification/replay/expected-divergences.yaml yet (token value is excluded from L3 diff
    entirely via diff-rules.yaml state_diff.exclude_columns — see that file's header for why;
    assert the CSPRNG property via verification/characterization/test_auth_reset.py::test_reset_token_is_not_md5_shaped
    instead, at L2)
  - statement: Dispatch the issued token by email via WO-004's boundary — NOT synchronously.
    fidelity: REPAIR — PB-001 (second call site, same disposition as WO-002).
    evidence: [legacy/app/server.py:94]   divergence: ED-002 (happy path), ED-003 (bypass-header
    path)
  - statement: Confirm redemption — a token that doesn't exist OR is >30 minutes old returns the
    IDENTICAL `403 invalid_token` body (deliberate non-disclosure). Valid unexpired token is
    deleted on success (single-use) and its email is returned.
    fidelity: FIXED — this is the one place legacy states its own security intent explicitly;
    preserve exactly, including after the PB-002 token-generation change.
    evidence: [legacy/app/server.py:98-108, verification/replay/traces/auth-reset.legacy.jsonl#reset-confirm-happy,
      #reset-confirm-expired, #reset-confirm-invalid-nonexistent, #reset-confirm-single-use]

acceptance:
  replay_set: verification/replay/corpus/auth-reset.requests.jsonl (all 7 traces; note
    reset-request-bypass-header cannot pass until OQ-001 is ruled and, if kept, the ruling's
    chosen auth mechanism is implemented — until then this WO stays awaiting_ruling)
  tests: verification/characterization/test_auth_reset.py (all except test_bypass_header_behavior,
    which is itself skipped pending OQ-001)
escalation: consult legacy/app/server.py:80-108 only.
