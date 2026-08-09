# WO-003 — Auth: password reset (PB-002 REPAIR site)

id: WO-003            depends_on: [WO-001]              milestone: M1
risk: 0.68 (inferred-claim ratio low but REPAIR-heavy: 2 REPAIRs [PB-001 async dispatch,
  PB-002 CSPRNG tokens] both resting on an UNSIGNED expected-divergences.yaml; 1 open ASK
  [OQ-007 bypass header] flags gate review; PB severity high on both defects; no legacy test
  coverage; security-sensitive surface)
usage_weight: 0.15 (static proxy — 2 routes, lower reference count than tickets, but the
  motivating defects live here)
pain_weight: 0.45 (PB-002 severity high, directly targets this WO; PB-001's SECOND call site is
  also here)
context_budget: ~450 lines (this WO + docs/features/draft/auth-reset.md +
  docs/domain/reset-token.md + relevant openapi.yaml paths + modern/CLAUDE.md's PB-001/PB-002
  architecture rules)
gate: true (PB severity high on 2 defects + unsigned expected-divergences.yaml — see below)

## STOP before implementing

`verification/replay/expected-divergences.yaml` is UNSIGNED (`ruled_by: null` on ED-001b,
ED-002). Per the executor loop, an L3 "pass" against an unsigned divergence manifest is not
trustworthy — the manifest exists to distinguish "intentional fix" from "regression," and nobody
has actually signed off on what "intentional" means here yet. Get a human to fill `ruled_by`/
`ruled_at` on both entries (or amend them) before treating this WO's L3 result as final. This is
exactly the kind of thing this WO's `gate: true` exists to force a stop for.

## Reading list

`docs/features/draft/auth-reset.md` (full behaviors, cited), `docs/domain/reset-token.md`
(entity + lifecycle diagram), `docs/open-questions.md#OQ-007` (bypass header), `modern/CLAUDE.md`
architecture rules (PB-001, PB-002), `verification/replay/expected-divergences.yaml` (ED-001b,
ED-002).

## Behaviors

- statement: rate limit 3/hour per email, `X-Internal-Bypass: 1` header skips it (undocumented —
  FIXED pending OQ-007 ruling, flags gate review, does not block this WO).
  fidelity: FIXED, flagged OQ-007
- statement: **PB-002** — token generation must move from MD5(email+time) to a CSPRNG
  (`secrets.token_urlsafe(32)` or equivalent). Storage/lookup mechanism otherwise unchanged
  (single-use, exact-match lookup, deleted on confirm).
  fidelity: REPAIR — divergence: ED-002 (UNSIGNED — see STOP above)
- statement: **PB-001** (second call site) — reset-request email dispatch must not block the
  response.
  fidelity: REPAIR — divergence: ED-001b (UNSIGNED — see STOP above)
- statement: confirm endpoint — identical `403 {"error":"invalid_token"}` for BOTH expired and
  unknown tokens. Preserve exactly; this is deliberate non-disclosure, not a bug.
  fidelity: FIXED — this is the one behavior in this WO that must NOT change even though it
  looks fixable. Do not "improve" it into separate error codes.
- statement: success response `200 {"ok": true, "email": ...}`; token deleted on use
  (single-use enforced).
  fidelity: FIXED

## Escalation

`legacy/app/server.py:80-108` only if citations are ambiguous.

## Acceptance

- L1: `/api/auth/reset`, `/api/auth/reset/confirm` validated against openapi.yaml.
- L2: `verification/characterization/test_auth_reset.py` full pass, INCLUDING
  `test_confirm_valid_token_consumes_it` (requires `TICKETD_DB_PATH` or an equivalent modern-side
  hook — if modern's DB isn't locally inspectable the same way, adapt the test's token-retrieval
  step, don't skip the assertion).
- L3: `verification/harness/diff-run.sh auth-reset` — all `auth-reset-*` traces pass, ED-001b and
  ED-002 diverging exactly as specified (once signed).
- Gate: STOP for human sign-off before closing — both on the unsigned ED entries above AND on
  OQ-007's bypass-header disposition (does the human want it carried forward? removed? that's
  their call, not this WO's).
