# WO-005 — Password-reset request (the PB-002 repair, part 1)

id: WO-005            depends_on: [WO-001, WO-004]  milestone: M2
risk: 0.72 (highest: security-flagged area; 2 REPAIRs + 1 open ASK; legacy churn hotspot —
  3 of 4 legacy commits are reset-flow hotfixes; no legacy test coverage)
usage_weight: 0.0195  pain_weight: 0.35             context_budget: ~400 lines   gate: true

Reading list: this file · `docs/contracts/openapi.yaml` (reset) · `docs/domain/reset-token.md`
· `docs/migration/target-schema.sql` (reset_tokens) · `expected-divergences.yaml#ED-002 #ED-003`
· `docs/open-questions.md#OQ-002` · `verification/harness/README.md` (age-token hook).

behaviors:
  - statement: body JSON, email defaults to ""; no format validation, no users-table
      existence check; empty email accepted and rate-limited under key "".
    fidelity: FIXED
    evidence: [ticketd/app/server.py:82-83, traces: t2-core#auth-reset-req-006]
  - statement: rate limit — if ≥3 requests for this email in the trailing 3600s → 429
      {"error":"rate_limited"}, no insert, no mail. Limit constants 3/hour.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:16-17,85-89, traces: auth-reset-req-001..004]
  - statement: header X-Internal-Bypass: 1 (exact value) skips the rate-limit check; the
      bypassed request still records a token row, which counts toward later non-bypassed
      checks.
    fidelity: ASK — open-questions.md#OQ-002 (blocks: none; flags this gate). Until ruled:
      implement exactly as legacy — replay freezes it (req-005 bypass OK at count 3;
      req-007 429 at count 3 post-bypass).
    evidence: [ticketd/app/server.py:84-92, traces: auth-reset-req-005/007]
  - statement: token generation/storage — legacy: md5(email + time.time()) hex stored
      cleartext in a bare table.
    fidelity: REPAIR (PB-002) — target: ≥128-bit CSPRNG token; only a hash at rest
      (SHA-256 per target-schema.sql — mechanism detail FREE); single-use and 30-minute
      expiry outcomes preserved (WO-006 verifies them); expired rows may be purged
      (DNP-003 — the accumulation must not be ported).
    evidence: [ticketd/app/server.py:90-92, ticketd/db/schema.sql:18-22, trace: auth-reset-req-001 state.token_store]
    divergence: ED-002 (state.token_store.cleartext true → false)
  - statement: mail to the requester, body "reset token: <token>", sent synchronously
      in-request in legacy.
    fidelity: REPAIR (PB-001, same mechanism as WO-004) — dispatch via the WO-004 outbox;
      body format/recipient outcome FIXED (token value redacted in traces).
    evidence: [ticketd/app/server.py:94, trace: auth-reset-req-001 state.email]
    divergence: ED-003 (state.email.mode sync → queued)
  - statement: success response 200 {"ok": true}; the token appears ONLY in the mail.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:95, trace: auth-reset-req-001]
  - statement: multiple live tokens per email allowed; each independently valid.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:91-92, characterization::test_multiple_live_tokens]

acceptance:
  replay_set: auth-reset-req-001..007 from t2-core (ED-002 + ED-003 apply)
  tests: verification/characterization/test_auth_reset.py (request-side tests,
         CHAR_TARGET=modern; requires modern/harness-age-token.sh)
gate_packet_note: surface OQ-002 for ruling; NFR-3 spot-check (token entropy, hash-at-rest)
  belongs in this gate review.
escalation: consult ticketd/app/server.py:80-95 only on ambiguity.
