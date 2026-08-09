# P9 Adversarial Audit — Discrepancy Report

Date: 2026-08-08. Auditor: fresh-context subagent, structurally independent — given ONLY the
pinned legacy tree, the problem brief, draft specs/WOs, contracts, and domain docs; no
generator reasoning, no verification/ artifacts. Four procedures per the P9 playbook:
falsification of FIXED claims, branch-coverage hunt, fixture spot-check, problem coverage.

## Verdict summary
- 35 FIXED claim instances checked → **31 confirmed, 2 contradicted, 2 unverifiable-in-scope**
- Every `ticketd/file:line` citation checked against source → all accurate (one wrong
  cross-reference between docs, A-10)
- Coverage gaps: 7 (3 substantive) — all now closed by spec additions
- Fixture errors: 0 (slugs re-derived by hand; shapes verified; dispatch events validate)
- Problem coverage: **PASS** — PB-001..004 all hold verifiable dispositions

## Findings and dispositions

| ID | verdict | finding (short) | disposition |
|---|---|---|---|
| A-01 | contradicted | Rate limit is over SURVIVING token rows, not requests — confirm DELETEs the row and frees quota; "4th request in an hour is rejected" is false after any confirm | Spec REWRITTEN (draft/auth-reset.md, WO-006, openapi.yaml 429). New replay set `ratelimit-refund` captured from legacy: rlr-request-004-after-refund observed 200, rlr-request-005 observed 429 — corrected semantics now empirically pinned. New L2 test `test_confirm_refunds_rate_limit` |
| A-02 | contradicted (FREE too broad) | Sanctioned purge-on-expiry would change 429 behavior — 30-60 min rows are unconfirmable but still counted | FREE grant NARROWED: purge only rows older than 3600s (draft + WO-006) |
| A-03 | missing | Empty `?status=` disables the filter (full dump), contradicting the openapi description | Spec statement added; openapi description fixed; probes rlr-list-empty-status(+with-row) captured — observed full-dump behavior |
| A-04 | missing | Valid-JSON non-object bodies (`[1]`, `"x"`, `5`) crash → 500 on all three JSON POSTs | Spec statements added (tickets + auth-reset drafts); sanctioned FREE→422 `request_invalid`; openapi 422 enum extended |
| A-05 | missing | The STRIPPED title is what persists/lists/exports/emails | FIXED statement added with trace evidence (tickets-list-001 pins it) |
| A-06 | missing (minor) | CSV row order unspecified (no ORDER BY; rowid in practice) | WO-007 pins insertion order via the golden trace |
| A-07 | contradicted | openapi.yaml used OAS-3.1 type arrays under `openapi: 3.0.3` | Converted to `nullable: true`; re-validated |
| A-08 | unverifiable | ED-004a/b modern bodies pinned nowhere contract-readable | 422 error enum (title_invalid, priority_invalid, request_invalid) added to openapi.yaml with pointer to the manifest |
| A-09 | unverifiable | ED naming drift (ED-004 vs ED-004a/b); ED definitions not referenced from docs | integration-notes.md corrected; manifest declared authoritative home |
| A-10 | contradicted | domain/ticket.md cross-referenced WO-004 for WO-003's edge cases | Fixed |
| A-11 | contradicted | auth-reset draft header claimed 'traced' impossible while WO-006 cites traces | Header rewritten |
| A-12 | missing (minor) | Float priority 2.0 → "2.0" → legacy 500; a pydantic model might silently coerce | Spec note added: never coerce non-integer numbers; 422 |
| A-13 | missing (minor) | Non-string reset email → 500 AFTER committed insert | Spec statement added; FREE→422 sanction |
| A-14 | ok-with-note | created_at DESC has no tie-break | FREE tie-break (id DESC) recorded in draft |
| A-15 | ok-with-note | DNP-005 said "shadowed" for a merely unused import | Wording fixed |

## Demotions
No claim required demotion to ASK: both contradicted claims were misstatements of behavior
that is unambiguous in source once re-read (A-01's correct semantics are cited AND now
T2-traced; A-02 is a constraint tightening). Per the P9 rule these were resolved by editing
the spec; the corrected statements carry the audit IDs inline so the correction trail
survives. Disputed-verdict escalations: none.

## Unverifiable-in-scope note
The auditor could not verify `trace:` citations or the harness boot-contract claims because
verification/ was outside its input set (by design — it is generator-authored and graded by
executing legacy, not by document review). Those claims are grounded by the harness runs
recorded in ledger.json `harness_baseline` (30/30 legacy self-diff; manifest
positive/negative simulations) rather than by this audit.

## Scope caveat
Audit coverage is code-only, like everything in this workspace: no runtime evidence existed
to audit against. The auditor's falsification power was limited to source reasoning; the
`ratelimit-refund` capture converted its strongest finding into executable evidence.
