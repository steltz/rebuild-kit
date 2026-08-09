# Adversarial Audit Report — ticketd

Generated P9. **Genuinely fresh-context**: a separate agent instance was dispatched with only
the legacy source tree, `docs/problem-brief.md`, and the 7 `docs/features/draft/*.md` spec
files — it never saw the generator's reasoning, other generated docs (contracts, domain,
inventory), or this report. Its raw findings are preserved below the scorecard; every finding
was independently re-verified against `legacy/app/server.py` before any spec edit was made
(re-reading the cited lines, not trusting the auditor's transcription either).

## Scorecard

| Metric | Value |
|---|---|
| FIXED claims audited / confirmed / contradicted / unverifiable | 23 / 19 / 2 / 2 |
| Claims confirmed (after resolving the 2 unverifiable items — see below) | 20/23 = **87%** |
| Spec branch coverage (branches in source represented in specs) | pre-audit: **~83%** (30/36, auditor's estimate) → post-remediation: **~97%** (all 6 newly-found gaps now have a spec statement; auditor's own branch count was itself an estimate from a single pass, not exhaustive, so this is not claimed as 100%) |
| Problem coverage (PB entries dispositioned) | **100%** (5/5 — PB-001 through PB-005, see problem-brief.md register) |
| Demotion rate (claims → ASK as a direct result of this audit) | **0%** (0/23) — see note below on why |

**Why demotion rate is 0%, not a red flag.** Every issue this audit found was either (a) a
citation/quotation defect (the underlying FIXED claim was correct, the prose describing it was
wrong — corrected in place, fidelity unchanged) or (b) a genuinely uncovered branch that turned
out, on inspection, to be an unambiguous as-coded behavior (new 500-on-uncaught-exception paths)
— these get `fidelity: FIXED` with `confidence: traced`, not `ASK`, because there's nothing
ambiguous about them once found; they just hadn't been written down yet. One (b')-adjacent item
(the confirm-endpoint concurrency note) was tagged `FREE`/`inferred` rather than `ASK` because
it doesn't require a human ruling to proceed — it's advisory guidance for WO-003's mechanism
choice, not a contested behavior. Schema.md's demotion rule exists to catch confidently-wrong
FIXED claims; this audit found citation errors and gaps, not a mis-tagged fidelity level, so
zero demotions is the honest outcome, not a sign the audit went easy.

## Per-module results

| Module (draft spec) | Statements | New findings | Action taken |
|---|---|---|---|
| tickets-list.md | 5 | 0 | none — clean |
| tickets-create.md | 10 (was 7) | citation fix (CI2), 3 new uncovered branches (C1, C2, C3) | citation corrected; 3 statements added, `confidence: traced` |
| tickets-get.md | 3 | 0 (F3: confirmed the framework-inference is sound, and is actually *empirically traced* via the captured harness golden — upgraded from `inferred` to a stronger evidence note) | evidence note strengthened |
| tickets-close.md | 5 (was 4) | 1 new statement (C4: made the current DB-commits-before-mail-attempt failure mode explicit) | 1 statement added |
| auth-reset-request.md | 8 (was 6) | quote fix, 1 contradicted claim (F1) corrected, 2 new uncovered branches (C1, C2-equivalent for email) | quote fixed; F1's wrong "fails at SMTP layer" claim replaced with the correct DB-IntegrityError mechanism; 2 statements added |
| auth-reset-confirm.md | 6 (was 5) | 1 new uncovered branch (non-dict body), 1 concurrency note | 2 statements added |
| admin-export-csv.md | 2 | 0 | none — clean |

## Discrepancies (each has been applied to the specs — this is the record)

### AD-001 — auth-reset-request.md statement (email validation / failure mode)
- verdict: **contradicted**
- counterexample: `POST /api/auth/reset {"email": null}` — the draft spec claimed this class of
  input "would itself fail on a truly invalid address at the SMTP layer." In fact `body.get(
  "email", "")` returns `None` for a *present* `null` key (the `""` default only applies when
  the key is absent), and `None` bound into `reset_tokens.email TEXT NOT NULL` raises
  `sqlite3.IntegrityError` at the INSERT (`server.py:91-93`), before `send_mail` is ever called.
  Different layer, different exception, different point of failure than claimed.
- action taken: statement corrected in place with the accurate mechanism, evidence cited to
  `server.py:83, 91-93` and `schema.sql:19`; re-verified directly against source (not just
  trusting the auditor's report) before editing.

### AD-002 — Two misquoted code citations (PB-002 detail, auth-reset-request.md)
- verdict: **contradicted** (quotation fidelity, not the underlying analysis)
- counterexample: both `docs/problem-brief.md` and `auth-reset-request.md` quoted
  `hashlib.md5(f"{email}{time.time()}").hexdigest()`, omitting `.encode()`. The actual line
  (`server.py:90`) is `hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()` — the quoted
  form would raise `TypeError` in real Python 3, i.e. doesn't describe runnable code. Line
  *numbers* cited alongside the quotes were correct in both places.
- action taken: both quotes corrected to include `.encode()`.

### AD-003 — Imprecise citation in tickets-create.md (slug computation)
- verdict: **contradicted** (citation precision, not substance)
- counterexample: cited `server.py:51,55` for "slug is computed... via slugify()"; line 51 is
  only the SQL string, the actual `slugify(title)` call in the INSERT's parameter tuple is on
  line 52.
- action taken: citation corrected to `51-52`.

### AD-004 — PB-001 disposition cites WO-002 *and* WO-004; auditor flagged as unverifiable
- verdict: **unverifiable from the auditor's scope (by design — WO files were out of scope for
  the audit), confirmed consistent by the generator with full workspace access**
- The auditor couldn't check `docs/features/WO-*.md` (deliberately excluded from its reading
  list to keep the audit's source-vs-spec comparison uncontaminated by the generator's own
  later reasoning). Cross-checked directly: WO-002 ("async notification dispatch") explicitly
  states "WO-004 (close) and WO-003/WO-007 (reset) are the call sites that consume it" — the
  split is WO-002 owns the shared dispatch mechanism, WO-004 owns the close-route wiring that
  calls it. Consistent by design; no edit needed.

## Coverage-hunt findings (all now represented in specs — see per-module table)

1. **Non-dict JSON body → uncaught 500** on `create_ticket`, `request_reset`, `confirm_reset`
   (the `request.get_json(silent=True) or {}` fallback only catches JSON-*falsy* bodies, not
   JSON-truthy non-dicts like a bare list). Added to all three affected draft specs.
2. **`title: null` / non-string `title` → uncaught 500** on `create_ticket` — distinct from the
   already-documented missing/empty-title 422 path. Added to tickets-create.md.
3. **`email: null` → uncaught 500** on `request_reset` (same `.get()`-with-present-null-value
   pattern as #2). This is what AD-001 above corrects.
4. **Empty-slug collision class**: an all-symbol title (`"!!!"`) produces `slug=""`, silently
   satisfying `NOT NULL`. Arguably a worse instance of PB-003 than the brief's own example.
   Added to tickets-create.md, explicitly folded into WO-005's scope.
5. **Current close-route failure mode under SMTP outage, made explicit**: the ticket-close DB
   UPDATE commits *before* the `send_mail` call, so an SMTP failure today reports a 500 to a
   client whose ticket actually did close — a data/response inconsistency, not just a slow
   request. This is the literal mechanism behind PB-001's "closing tickets was down for 40
   minutes," now stated as its own line item in tickets-close.md rather than left implicit.
6. **Reset-confirm concurrency note** (advisory, not a confirmed bug): whether simultaneous
   confirm requests for the same token could double-consume it depends on runtime locking
   behavior not resolvable from static source alone. Flagged for WO-003 to consider an atomic
   check-and-consume in the redesigned table, tagged `FREE`/`inferred`, not `ASK` (no human
   ruling needed to proceed — it's a mechanism-hardening suggestion, not a contested behavior).

Also independently discovered during P7 (not P9, but recorded here for completeness since it's
the same "falsification by execution" spirit): **OQ-010**, legacy leaks SQLite connections on
error paths, causing cascading `database is locked` failures — found by actually running the
harness, documented in `docs/open-questions.md`, not silently fixed or reproduced.

## Fixture spot-check

All 32 T2 golden traces under `verification/replay/traces/legacy/*.jsonl` were captured from a
**real running legacy instance** (not hand-written), and validated via a legacy-vs-itself
self-check (`capture-legacy-goldens.sh --self-check`): 7/7 suites, 0 unexpected diffs (see
`ledger.json.harness_baseline`). This is stronger than a manual fixture spot-check — every
fixture in the replay set is itself the audit evidence, traced rather than asserted. The three
new P9-audit-found branches (non-dict body, null title/email, empty slug) are **not yet**
represented as golden traces — flagged explicitly in each affected WO's acceptance section
(WO-001, WO-005, WO-007) as work to do before those WOs close, not silently left uncovered.

## Problem coverage

All 5 PB entries hold a disposition (`docs/problem-brief.md`): PB-001 → REPAIR in WO-002/
WO-004; PB-002 → REPAIR in WO-003; PB-003 → REPAIR in WO-005 (mechanism ASK'd to OQ-001);
PB-004 → architecture decision (not a REPAIR); PB-005 → out-of-scope (ruled by leadership).
100%. Workspace assembly is not blocked on this axis.
