# Adversarial Audit — ticketd

<!-- Generated P9. Fresh-context auditor: a separate agent invocation given ONLY legacy/, the
     problem brief, and docs/features/draft/*.md -- no access to this generator's reasoning,
     notes, or the rest of the workspace (contracts, domain docs, backlog). This is the "approxi-
     mate independence" mode the skill calls for when running serially without a full multi-agent
     workflow: a genuinely separate context, not a self-review. Findings below are AS REPORTED by
     that auditor, independently spot-verified against legacy source by the generator before
     being applied as corrections (see each finding's "verified" note). -->

## Scorecard

| Metric | Value |
|---|---|
| Claims audited (pre-audit draft-spec statements) | 28 |
| Confirmed outright | 26 |
| Confirmed, citation corrected | 1 (F-2) |
| Contradicted, corrected in place | 1 (F-1) |
| New claims added via coverage hunt | 1 (C-1/C-2, merged) |
| Problem coverage (PB entries dispositioned) | 2/2 = 100% |
| Demotion rate (existing FIXED/REPAIR claims demoted to ASK) | 0/28 = 0% (the one contradiction was corrected in place, not demoted — see F-1; the coverage-hunt addition was ASK from creation, not a demotion of a prior claim) |
| Open-questions register integrity issues found and fixed | 2 (I-1: a referenced-but-unfiled OQ; I-2: 2 OQ entries never cross-referenced from the specs they gate) |

**Branch coverage**: the auditor read every line of every legacy file (165 LOC total — small
enough for exhaustive review, not sampling) and confirmed every route/branch/edge case has a
corresponding spec statement AFTER the two coverage-hunt items (C-1, C-2) were added. Before the
audit: 2 real gaps existed. After: 0 known gaps.

## Per-module results

| Module | Claims | Confirmed | Demoted | New coverage items | Notes |
|---|---|---|---|---|---|
| Tickets: list/create/get | 11 | 9 confirmed outright, 1 citation-corrected, 1 contradicted-and-corrected | 0 | +1 (C-1/C-2) | Highest-finding-density module — see F-1, F-2, C-1, C-2, I-1 below |
| Tickets: close | 4 | 4 | 0 | 0 | Clean — commit-before-send ordering explicitly re-verified line-by-line |
| Auth: reset | 10 | 10 | 0 | 0 | Clean — MD5 mechanism, rate limit math, non-disclosure body all re-verified exactly |
| Admin: CSV export | 3 | 3 | 0 | 0 | Clean |
| do-not-port.md (legacy_import.py) | n/a | confirmed | n/a | n/a | Zero-reference claim independently re-verified |

## Discrepancies (each has been applied to the specs — this is the record)

### AD-001 — GET /api/tickets status-filter trigger condition (tickets-list-create-get.md)
- verdict: contradicted
- counterexample: `GET /api/tickets?status=` (param present, value empty). `if status:`
  (`legacy/app/server.py:32`) is falsy for `""`, so the filter is silently skipped and ALL
  tickets return — not filtered to `status=''`, and not distinguishable from omitting the param.
  The original spec said "when present," which this case falsifies (present but ignored).
- action taken: statement corrected in place in `docs/features/draft/tickets-list-create-get.md`
  to say "truthy," not "present," with the empty-string case spelled out explicitly. Fidelity
  stays FIXED — this is real, evidenced, unambiguous legacy behavior, just previously
  mis-described, not a case for REPAIR or ASK.

### AD-002 — slug-derivation citation range off by one line (tickets-list-create-get.md)
- verdict: confirmed, evidence imprecise
- gap: cited range `legacy/app/server.py:50-51` for "`slug` is derived via `slugify(title)`" —
  line 50 is the `db().execute(` call, line 51 is the SQL string; the actual `slugify(title)`
  call is on line 52, inside the params tuple.
- action taken: citation corrected to `legacy/app/server.py:52` in the spec file. Claim itself
  was true throughout; only the citation range was wrong.

### AD-003 — Two crash paths with no prior spec coverage (tickets-list-create-get.md)
- verdict: unverifiable coverage gap (not a false claim — an absent one)
- gap: (a) a non-string `title` (e.g. `{"title": 5}`, `{"title": null}`) hits `.strip()` at
  `legacy/app/server.py:43` and raises an unhandled `AttributeError` (Flask default 500); (b) an
  EXPLICIT `{"priority": null}` does not receive the `"med"` default (which only applies when
  the key is absent) and becomes the literal string `"None"` via `str(None)` at line 47,
  falling into the same untested invalid-priority path already flagged (now `OQ-008`).
- action taken: new spec statement added, tagged `ASK`, filed as
  `docs/open-questions.md#OQ-009` — including the auditor's own follow-on observation that a
  Pydantic-based FastAPI rewrite may reject these at the validation layer automatically, which
  would make "porting today's 500" not straightforwardly achievable (worth a human's attention,
  not a mechanical port decision).

### AD-004 — Referenced-but-never-filed OQ (register integrity)
- verdict: contradicted (internal inconsistency, not a legacy-behavior claim)
- gap: the draft spec's invalid-priority statement said "no existing OQ covers it" as a promise
  to file one, but `docs/open-questions.md` had no matching entry at audit time.
- action taken: filed as `docs/open-questions.md#OQ-008`, spec statement updated to point at it.

### AD-005 — Two OQ entries never cross-referenced from the specs they gate
- verdict: contradicted (internal inconsistency)
- gap: `OQ-004` (no auth/session layer anywhere in the app) and `OQ-006` (reset_tokens rows
  never purged) existed in the register but were never linked FROM
  `tickets-list-create-get.md`, `tickets-close.md`, `admin-export-csv.md` (OQ-004, every route
  in all three is unauthenticated) or `auth-reset.md` (OQ-004 and OQ-006 both apply).
- action taken: cross-reference notes added to all four draft spec files.

## Coverage-hunt findings

See AD-003 above — the only branches found with no prior spec representation. Everything else in
the 165-line legacy tree (7 routes, `db()` helper, `__main__` block, `legacy_import.py`) was
independently re-derived by the auditor and matched the existing specs.

## Fixture spot-check

Not re-run by the fresh-context auditor (fixtures live under `docs/contracts/`, outside its
restricted reading list by design — contract validation was already done mechanically in P5, see
`docs/contracts/fixtures/validation-log.txt`, and re-confirmed after the P9 openapi.yaml rewrite:
11/11 fixtures pass against the component schemas using `scripts/validate_fixtures.py`, plus
`openapi-spec-validator` confirms the file is valid OpenAPI 3.0.3).

## A note on independence

This audit's "fresh context" was a separate agent invocation restricted to legacy/, the problem
brief, and the draft specs — it could not see `docs/domain/`, `docs/contracts/`, `backlog.md`, or
this generator's reasoning. Its findings (F-1 through I-2 above, renumbered AD-001 through
AD-005) were independently re-verified against legacy source by the generator (via direct
`sed`/read of the cited lines) before being applied — not accepted on the auditor's word alone,
consistent with "no arguing with the auditor in the artifacts; a disputed verdict is itself an
ASK." No finding was disputed; all were confirmed and applied.
