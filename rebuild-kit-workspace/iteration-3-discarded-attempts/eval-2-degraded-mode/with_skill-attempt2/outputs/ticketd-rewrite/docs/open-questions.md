# Open Questions — ASK register & PB proposals

<!-- Executor + generator both append here. Never delete entries; rulings are appended.
     Each new OQ gets a ruling brief generated into guide/briefs/ (templates/ruling-brief.md). -->

## OQ-001 — Is the `200 {}` response for a missing ticket load-bearing?
- raised_by: generator P0 (intake gap; formalized P4)
- kind: ambiguity
- readings:
  - A: The code comment is explicit and intentional — "historical quirk: 200 with empty object,
    NOT 404 — the legacy UI depends on it" (`legacy/app/server.py:62-63`). Preserve exactly
    (FIXED) since an unseen frontend may depend on it.
  - B: No legacy frontend was included in the handover, so "the legacy UI depends on it" cannot
    be verified. A rewrite is a natural point to fix this to a standard 404, if no consumer
    actually needs the old shape.
- blocks: [WO-003] (ticket-read endpoint) — WO-003 defaults to reading A (preserve) until ruled.
- ruling: PENDING

## OQ-002 — Is the dual int/string `priority` encoding still required?
- raised_by: generator P0 (intake gap; formalized P4)
- kind: ambiguity
- readings:
  - A: Comment states "priority is accepted as int or string — clients send both, both must keep
    working" (`legacy/app/server.py:46-49`). Preserve exactly (FIXED).
  - B: No client code was handed over to confirm which callers send which form, or whether both
    are still live.
- blocks: [WO-003] (ticket-create endpoint) — WO-003 defaults to reading A until ruled.
- ruling: PENDING

## OQ-003 — What scale/SLO/operability targets apply?
- raised_by: generator P0 (intake gap)
- kind: inferred-only
- readings:
  - A: No pagination on `GET /api/tickets` (`legacy/app/server.py:35-37`, comment: "the UI relies
    on getting everything and filtering client-side") implies low ticket volume, single
    internal-tool deployment.
  - B: Unknown — no explicit scale/SLO testimony was given at intake.
- blocks: [] (flags gate review only — affects whether WO-003's list endpoint should add
  pagination as a FREE improvement or preserve unpaginated-FIXED behavior)
- ruling: PENDING

## OQ-004 — Is the undocumented `X-Internal-Bypass` header on `/api/auth/reset` intentional?
- raised_by: generator P0 (intake gap; formalized P4), kind promoted from pb-proposal candidate
- kind: pb-proposal
- readings:
  - A: It's an intentional operational escape hatch (e.g. for internal tooling or test
    automation) that skips the 3/hour rate limit on password-reset requests
    (`legacy/app/server.py:84-89`). If so, the rewrite should formalize it as an authenticated
    internal-service allowlist, not a magic header value.
  - B: It's leftover debug/test code with no legitimate production use, and should be removed —
    it currently lets anyone who knows the header value bypass reset rate-limiting.
- blocks: [WO-001] (reset-token endpoint) — WO-001 defaults to preserving the bypass, disabled by
  default in `modern/` config, pending ruling. **Not silently ported active-by-default.**
- ruling: PENDING

## OQ-005 — Are naive local-time timestamps (`created_at`/`closed_at`) an accepted limitation?
- raised_by: generator P0 (intake gap; formalized P4), kind promoted from pb-proposal candidate
- kind: pb-proposal
- readings:
  - A: `datetime.now().isoformat()` with no timezone (`legacy/app/server.py:52`, self-flagged in
    a code comment: "naive local time!") is a known, accepted quirk — the contractor was aware
    and it never caused a reported incident.
  - B: It's an unrecognized bug (server-timezone-dependent timestamps) that should be fixed to
    UTC-aware timestamps in the rewrite, since nothing in the handover notes says it's
    intentional or acceptable.
- blocks: [] (flags gate review; WO-003/WO-001 default to reading B — store UTC-aware
  timestamps in Postgres `timestamptz` — since this is a Postgres migration regardless and
  `timestamptz` is the idiomatic FREE choice; flagged here because it IS an observable behavior
  change from legacy and needs a ruling to convert from "unsanctioned" to "sanctioned via OQ-005"
  rather than a REPAIR silently invented from a PB)
- ruling: PENDING

## OQ-006 — Should `app/legacy_import.py` be ported?
- raised_by: generator P0 (intake gap; formalized P3), kind promoted from pb-proposal candidate
- kind: pb-proposal
- readings:
  - A: It's confirmed dead code — docstring states "Nothing imports this module," and a
    repo-wide search confirms no references anywhere in `legacy/`. It should be listed in
    `docs/do-not-port.md` and not ported.
  - B: It may still be run manually/out-of-band (e.g. ops runbook) even though nothing in-repo
    calls it, which the static analysis in this workspace cannot see (no access logs, no ops
    runbook was handed over).
- blocks: [] — defaulted to reading A (do-not-port, see `docs/do-not-port.md`) since the evidence
  bar for negative space is "zero-traffic + zero-references," and zero-references is confirmed;
  zero-traffic cannot be confirmed (P2 inactive). Flagged for gate review, not blocking.
- ruling: PENDING

## OQ-007 — Upgrade evidence tier once production DB/log access lands
- raised_by: generator P0
- kind: inferred-only
- readings:
  - A: The requester expects production DB access "in a few weeks." At that point, P2 (runtime
    evidence) and P6 (data census) should be re-run per `references/phases/spec-patch.md`,
    upgrading affected claims from T3 to T1/T2 and re-scoring risk in `ledger.json`.
  - B: (none — this is a scheduling/process note, not a genuine ambiguity, but is tracked here so
    it isn't lost)
- blocks: [] — flags a milestone-close review point once M0 evidence-upgrade becomes possible.
- ruling: PENDING

## OQ-008 — Unmapped `priority` values crash the create-ticket request (500)
- raised_by: generator P3 (`docs/domain/ticket.md`), kind: pb-proposal
- kind: pb-proposal
- readings:
  - A: `POST /api/tickets` only maps the strings `"1"`/`"2"`/`"3"` to `low`/`med`/`high`
    (`legacy/app/server.py:47-49`); any other value (e.g. `"urgent"`, `"4"`, `""`) is passed
    straight through to the INSERT, which hits the sqlite `CHECK (priority IN (...))` constraint
    (`legacy/db/schema.sql:5`) and raises an unhandled `sqlite3.IntegrityError`, surfacing as an
    unstructured 500. This looks like an unrecognized bug — no PB backs it, and it isn't
    self-flagged in a comment the way OQ-005's naive-datetime issue is.
  - B: It may be intentional/accepted — client code (not in this handover) might only ever send
    the three sanctioned values, making this dead-path defensive-programming debt rather than a
    live bug.
- blocks: [WO-003] (ticket-create endpoint) — WO-003 defaults to preserving the crash-on-bad-input
  behavior as FIXED (Design Principle 9: no PB sanctions a fix), but returns it as a clean 422
  instead of an unhandled 500 IS a candidate REPAIR if ruled — draft WO-003 documents both paths.
- ruling: PENDING
