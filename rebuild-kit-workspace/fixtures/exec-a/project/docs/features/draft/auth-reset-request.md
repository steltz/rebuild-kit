# Draft spec: POST /api/auth/reset (request a reset token)

usage_weight: 0.0195 · perf envelope (low-confidence): p50 92ms / p95 212ms / p99 306ms —
again notably slower than list/create, consistent with the synchronous SMTP call here too.

## Behaviors

- statement: Rate limit: if the request does not carry header `X-Internal-Bypass: 1`, and 3 or
    more `reset_tokens` rows already exist for this `email` with `created_ts` in the last 3600
    seconds, respond `429 {"error": "rate_limited"}` and stop (no token issued, no email sent).
  fidelity: FIXED
  evidence: [legacy/app/server.py:84-89]
  confidence: cited (traced: exactly 1 `429` observed in the sampled access log, out of 39
    reset-request calls — consistent with the rate limit firing rarely under light,
    single-user-looking traffic; low confidence per the log's synthetic-window caveat)

- statement: `X-Internal-Bypass: 1` skips the rate-limit check entirely, regardless of caller
    identity (there is no additional check gating who may send this header).
  fidelity: ASK — OQ-006. Preserve the header's existence and effect exactly as-is
    (do not remove it) until ruled; do not add gating logic unilaterally either.
  evidence: [legacy/app/server.py:84]
  confidence: cited

- statement: A token is generated as `hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()` and
    inserted into `reset_tokens(email, token, created_ts)` unconditionally (even for an `email`
    with no matching `users` row — no such check exists, see docs/domain/user.md).
  fidelity: REPAIR in WO-003 — target: CSPRNG-generated token, stored hashed (PB-002).
  evidence: [legacy/app/server.py:90-93]
  confidence: cited
  divergence: ED-002

- statement: The generated (plaintext) token is emailed to the caller-supplied `email` address
    with body `f"reset token: {token}"`, **synchronously, inside the request**.
  fidelity: REPAIR in WO-002/WO-003 — target: async dispatch (PB-001); token itself no longer
    plaintext-MD5 (PB-002) but the *email containing a usable token* behavior is FIXED (that's
    the feature).
  evidence: [legacy/app/server.py:94, legacy/app/notify.py:1-7]
  confidence: cited
  divergence: ED-001 (dispatch mechanism), ED-002 (token mechanism)

- statement: Response is always `200 {"ok": true}` regardless of whether `email` corresponds to
    a real user — the route never discloses whether an address is registered.
  fidelity: FIXED — this is good practice already in place (enumeration resistance) and must
    survive both REPAIRs above unchanged.
  evidence: [legacy/app/server.py:95]
  confidence: cited

- statement: `email` is read from the JSON body (`body.get("email", "")`) with no format
    validation at all — an empty string, a malformed address, or any arbitrary string is
    accepted and stored/emailed-to as-is.
  fidelity: FIXED (no validation, as coded) — but note this interacts with WO-002's async
    REPAIR: once dispatch is out-of-band, whatever failure mode exists today for a bad address
    (see the corrected statement below — it is NOT an SMTP-layer failure) can no longer surface
    as a request-time error at all once mail is queued out-of-band. This needs an explicit
    decision in WO-002/WO-003 about whether malformed emails fail fast (422) or are silently
    accepted and fail silently downstream — **not specified by the brief**, flag as an
    implementation question for WO-002, not a new PB.
  evidence: [legacy/app/server.py:82-83]
  confidence: cited

- statement: **CORRECTED after P9 audit (was previously mis-stated).** `email: null` (the JSON
    key present with a literal `null` value, as opposed to the key being absent) does NOT reach
    `send_mail` at all and does NOT fail "at the SMTP layer" as an earlier draft of this spec
    incorrectly claimed. `body.get("email", "")` returns Python `None` when the key is present
    with value `null` (the default `""` only applies when the key is *absent*). This `None` is
    bound directly into `INSERT INTO reset_tokens (email, ...)` against a column declared
    `email TEXT NOT NULL` — raising an uncaught `sqlite3.IntegrityError` → 500, **before**
    `send_mail` is ever reached. Contrast with a missing `email` key entirely, which correctly
    defaults to `""` and proceeds (an empty-string email is accepted and "sent to" today, per
    the FIXED statement above).
  fidelity: FIXED (as-coded gap; not brief-mentioned, not silently hardened)
  evidence: [legacy/app/server.py:83 (`body.get("email", "")` semantics), :91-93 (INSERT),
    legacy/db/schema.sql:19 (`email TEXT NOT NULL`)]
  confidence: traced (found empirically via P9 adversarial audit falsification pass, not
    originally cited; corrects a wrong claim in an earlier draft of this same spec)

- statement: A JSON body that parses successfully but is not a dict (e.g. a bare list, string,
    number, or boolean — anything JSON-truthy) is NOT caught by `request.get_json(silent=True)
    or {}`, since the `or {}` fallback only triggers on JSON-*falsy* values (`[]`, `""`, `0`,
    `false`, `null`). A truthy non-dict body therefore reaches `body.get("email", "")`, which
    raises `AttributeError` on a non-dict → uncaught 500.
  fidelity: FIXED (as-coded gap, undocumented, not brief-mentioned)
  evidence: [legacy/app/server.py:82-83]
  confidence: traced (P9 audit finding — same pattern affects `create_ticket` and
    `confirm_reset`, see their respective draft specs)

## Acceptance
  replay_set: auth-reset-request-*.jsonl (happy path, rate-limited, bypass-header honored,
    missing email, malformed email) — **not yet extended** to cover the two P9-audit findings
    above (`email: null`, non-dict body); add before WO-007 closes.
  tests: characterization/auth/reset-request.spec
