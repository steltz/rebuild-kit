# Verification

Two layers: an executable **contract suite** (`contract_tests/`) and a manual/operational
**acceptance checklist** (below). The rewrite is done when the suite is green against
ticketd-ng and every checklist item is checked.

## Contract suite

`contract_tests/test_contract.py` is black-box: it talks HTTP to whatever
`TICKETD_BASE_URL` points at, so it can run against **legacy** (to validate the tests
encode reality) and against **ticketd-ng** (to validate the rewrite). Tests that encode
deliberate CHANGEs are marked `@new_only` and auto-skip when `TICKETD_LEGACY=1`.

```bash
cd rewrite/verification/contract_tests
python -m venv .venv && .venv/bin/pip install pytest httpx

# Against legacy (from ticketd/, needs a db/ticketd.sqlite3 created from schema.sql):
TICKETD_BASE_URL=http://127.0.0.1:5000 TICKETD_LEGACY=1 .venv/bin/pytest -v

# Against the new service:
TICKETD_BASE_URL=http://127.0.0.1:8000 .venv/bin/pytest -v
```

The suite mutates data (creates/closes tickets, requests resets) — run against disposable
databases only. It cannot verify email delivery (black-box); that is checklist V-5/V-6.

Sections: T1 list, T2 create, T3 get, T4 close, T5 reset, T6 confirm, T7 removed
endpoints, T8 error shapes.

## Acceptance checklist

Compatibility
- [ ] **V-1** Contract suite green vs legacy with `TICKETD_LEGACY=1` (tests encode reality
      — do this FIRST, before building anything; fix tests, not legacy, on mismatch).
- [ ] **V-2** Contract suite green vs ticketd-ng.
- [ ] **V-3** `GET /api/tickets/{missing}` returns `200 {}` on ng (the quirk survived —
      also in suite; called out because it is the most tempting thing to "fix").
- [ ] **V-4** Numeric (`3`/`"3"`) and word (`"high"`) priorities both create tickets on ng.

Notifications (the June-outage fix)
- [ ] **V-5** Close a ticket with SMTP sink up → email arrives with body `closed: <title>`
      to `watchers@example.internal`; reset request → `reset token: <token>` to requester.
- [ ] **V-6** SMTP sink DOWN: close 5 tickets → all respond 200 `{"closed": true}` in
      <500 ms; bring sink up → all 5 emails delivered within 2 backoff cycles; outbox has
      no unsent rows afterward.
- [ ] **V-7** Kill and restart the API + worker between an accepted close and delivery →
      email still delivered (durability across restart).
- [ ] **V-8** Already-closed ticket re-closed → `{"closed": false}` and NO new outbox row.

Security (reset tokens)
- [ ] **V-9** All items in `specs/05-security-reset.md` acceptance checklist pass
      (no md5, hashed at rest, atomic single-use, identical 403 bodies, 429 on 4th/hour).

Timestamps (Q5)
- [ ] **V-10** Confirmed with stakeholders (or default taken and recorded): svc-ui renders
      naive-UTC `created_at` acceptably; `--source-tz` for migration is known.

Migration
- [ ] **V-11** Migration verification report: row counts, id ranges, status/priority
      histograms, (id,title,status) checksum all match source; sequences advanced past
      max(id) (create a ticket immediately after migration — no PK conflict).
- [ ] **V-12** Legacy `reset_tokens` NOT migrated; ng table starts empty.
- [ ] **V-13** Synthetic edge-case SQLite (colliding slugs, NULL priority, unicode titles)
      migrates cleanly with repairs logged.

Cutover
- [ ] **V-14** Staging soak: contract suite + V-5..V-8 green on staging.
- [ ] **V-15** Post-cutover smoke: create / list / get-missing / close-with-email / full
      reset round-trip on prod.
- [ ] **V-16** 48 h monitoring: 500-rate below legacy baseline (~2.5%), pending-outbox age
      alert quiet, no gateway errors.
- [ ] **V-17** Every question in `decisions/open-questions.md` has a filled-in Resolution.

Slug decision (Q1)
- [ ] **V-18** Q1 resolved and implemented; if Option A: two tickets titled "Fix DB" and
      "fix db!" get distinct slugs; legacy duplicates renumbered during migration with a
      rename log.
