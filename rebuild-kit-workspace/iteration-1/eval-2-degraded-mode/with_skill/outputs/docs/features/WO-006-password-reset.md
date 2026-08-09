# WO-006 — Password-reset flow (PB-002 repair + PB-001 call site 2)

id: WO-006            depends_on: [WO-001, WO-004]    milestone: M2
risk: 0.65 (two REPAIRs + one ASK-flagged behavior + purpose ambiguity OQ-002; security-
  sensitive; highest inferred-density in the workspace)          gate: true (M2 gate)
usage_weight: 0.14 (static-proxy, both endpoints)   pain_weight: 0.8 (PB-001 + PB-002, both high)
context_budget: ~400 lines (this WO + draft/auth-reset.md + domain/reset-token.md +
  openapi.yaml auth paths + fixtures/auth-reset.json)

behaviors:
  - statement: POST /api/auth/reset — email unvalidated (any string incl. empty; never
      checked against users); response always `{"ok": true}` 200 when not rate-limited
      (account-enumeration-safe); token travels ONLY in the email.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:82-95, trace: reset-request-001,
      reset-request-006-unknown-email]
  - statement: Rate limit — 429 `{"error":"rate_limited"}` when ≥3 SURVIVING rows for that
      email sit in reset_tokens with created_ts in the last 3600s, counted pre-insert.
      Confirming a token deletes its row and FREES quota; expired-but-unconfirmed rows
      (30-60 min) still count. [Corrected by audit A-01.] Implementation must count the
      token store (or an exactly equivalent structure), not a request log.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:16-17,84-89,106, trace: reset-request-004-ratelimited,
      ratelimit-refund replay set (refund + empty-window probes)]
  - statement: `X-Internal-Bypass: 1` skips the rate limit. Implement PARITY behind config
      flag RESET_RATE_LIMIT_BYPASS_ENABLED (default ON so replay passes). Intent unknown —
      undocumented, unauthenticated.
    fidelity: ASK — open-questions.md#OQ-004 (blocks: none; flags M2 gate review — the
      owner decides keep/kill at the gate; killing it is a one-line flag flip + ED entry)
    evidence: [ticketd/app/server.py:84, trace: reset-request-005-bypass]
  - statement: Token generation/storage — CSPRNG presentable token (secrets, ≥128-bit),
      stored HASHED (sha256+) with created_at; presentable value only in the email. Multiple
      live tokens per email remain valid concurrently (legacy behavior, kept).
    fidelity: REPAIR — PB-002 (legacy: md5(email+time) plaintext at rest);
      divergence: ED-003. Concurrent-validity outcome: FIXED
      [ticketd/app/server.py:90-92 — no invalidation of earlier tokens].
    evidence: [ticketd/app/server.py:90-92, ticketd/db/schema.sql:18-22,
      trace: session-end-state (reset_token_storage: md5-plaintext observed)]
  - statement: Token email dispatched via WO-004's seam (marker `reset token: <token>`),
      never in-request.
    fidelity: REPAIR — PB-001; divergence: ED-002
    evidence: [ticketd/app/server.py:93-94, trace: reset-request-001 (mode sync observed)]
  - statement: POST /api/auth/reset/confirm — lookup by token only; unknown OR >30-min-old
      → 403 with IDENTICAL body `{"error":"invalid_token"}` (deliberate non-disclosure);
      valid → consume (single-use), 200 `{"ok": true, "email": <requested email>}`.
      RESET_WINDOW_MIN=30 stays 30.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:16,100-108, trace: reset-confirm-001..005]
  - statement: Expired-token retention/purge policy — purge ONLY rows older than 3600s
      (audit A-02: rows aged 30-60 min are unconfirmable yet still rate-limit-relevant, so
      an eager purge changes observable 429s). Outcomes: expired tokens unusable AND
      rate-limit counts unaffected. Migration decision in docs/migration/mapping.md.
    fidelity: FREE (narrowed)
    evidence: [ticketd/app/server.py:85-88 vs :103 — 3600s count window vs 1800s validity]

## Context for the gate (not implementation guidance)
OQ-002: no code consumes the confirmed email — `users` has no password column and there is
no login endpoint. The flow is implemented to observed behavior regardless; the gate review
decides whether it should exist at all.

acceptance:
  replay_set: core.jsonl → traces reset-* + session-end-state must pass (ED-002, ED-003 apply)
  tests: characterization TestResetFlow (all, incl. test_confirm_refunds_rate_limit —
    the A-01 corrected semantics)
gate_packet: guide/briefs/gate-M2.md — OQ-002/OQ-004 rulings requested, ED signatures
escalation: ticketd/app/server.py:80-108 (the entire flow, 29 lines)
