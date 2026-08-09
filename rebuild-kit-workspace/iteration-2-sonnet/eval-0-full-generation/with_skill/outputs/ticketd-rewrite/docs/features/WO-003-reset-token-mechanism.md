id: WO-003            depends_on: [WO-001, WO-002]         milestone: M1
risk: 0.72 (PB severity high (security-flagged); inferred-claim ratio low (well-evidenced);
  complexity: medium; legacy coverage: none; churn: reset flow was hotfixed 3x in legacy history
  with no test coverage added — see hotspots.md — historically fragile area)
usage_weight: 0.0195+0.01 = 0.0295 (auth/reset request + confirm combined)
pain_weight: 0.9 (PB-002, severity high, security-flagged)
context_budget: ~400 lines (this WO + docs/domain/reset_token.md + docs/migration/mapping.md's
  reset_tokens section + docs/contracts/openapi.yaml auth paths)
gate: true

## What this WO does
Replace the MD5-of-email-plus-timestamp token mechanism and bare unindexed table with a
CSPRNG-generated, hashed-at-rest token in a properly keyed table (PB-002). Covers token
generation and storage only; WO-007/WO-008 wire the request/confirm HTTP handlers to use it
(kept separate so this WO's schema+crypto decisions can be reviewed on their own).

behaviors:
  - statement: "Tokens must be drawn from a cryptographically secure random source, not
      derived from user-controllable or guessable/knowable input (legacy: md5(email+time.time()))."
    fidelity: REPAIR — ratified by PB-002.
    evidence: [legacy/app/server.py:90, docs/problem-brief.md PB-002]
  - statement: "The raw token value must never be stored — only a hash of it (e.g. SHA-256),
      alongside an expiry timestamp enforced at the DB level in addition to app-level checks."
    fidelity: REPAIR — ratified by PB-002.
    evidence: [legacy/db/schema.sql:18-22 (bare table, no PK/index/expiry), docs/domain/reset_token.md]
    divergence: ED-002 (see verification/replay/expected-divergences.yaml notes — no response
      body ever carries the token, legacy or modern, so there's no response-field-level ED
      entry to write against the token VALUE; diff-rules.yaml already excludes
      reset_tokens.token from db_dump state comparison outright. What this WO's acceptance DOES
      need: a characterization test asserting the new token is NOT MD5-hex-shaped (32 lowercase
      hex chars) as a regression guard — see acceptance below.)
  - statement: "Single-use: the token (or its DB row) becomes unusable immediately after a
      successful confirm. Non-disclosure: invalid and expired tokens produce IDENTICAL
      responses. Expiry window: 30 minutes."
    fidelity: FIXED — these three legacy behaviors must survive the mechanism REPAIR unchanged.
    evidence: [legacy/app/server.py:99-108, docs/domain/reset_token.md]
  - statement: "Table schema, ORM model, whether 'used' is represented by deletion vs. a
      consumed_at column."
    fidelity: FREE — see docs/migration/mapping.md's proposed reset_tokens DDL for a reasonable
      default (not a ruling).
  - statement: "No rate limiting exists today on the CONFIRM endpoint (unlike request, which
      does rate-limit). Whether to add it is OQ-009, unruled."
    fidelity: ASK — OQ-009. Do not add confirm-endpoint rate limiting as part of this WO
      without a ruling; it would be unsanctioned scope beyond PB-002's stated target.
    evidence: [legacy/app/server.py:98-108, docs/open-questions.md OQ-009]

acceptance:
  replay_set: auth-reset-confirm-*.jsonl, auth-reset-request-*.jsonl (already captured T2
    goldens; NOTE these traces' request.body.token field is normalized/dropped in diff-rules.yaml
    specifically because it's expected to look structurally different post-REPAIR — see that
    file's inline comment). The STATUS CODES and non-token response fields in these goldens
    (200/403/429 and their bodies minus token) remain the FIXED acceptance bar.
  tests: verification/characterization/test_against_golden.py (parametrized) PLUS a new,
    hand-written test asserting the generated token is NOT 32-char-lowercase-hex (regression
    guard against silently reverting to an MD5-shaped value) and that reset_tokens.token (raw)
    is never queryable/present in the DB (only a hash column is)
  l1: docs/contracts/openapi.yaml auth paths (unchanged request/response shapes)
  l3: verification/harness/diff-run.sh auth-reset-confirm && diff-run.sh auth-reset-request

escalation: consult legacy/app/server.py:80-108 in full (both routes together — the token
  lifecycle only makes sense read as one unit) plus legacy/db/schema.sql:18-22.
