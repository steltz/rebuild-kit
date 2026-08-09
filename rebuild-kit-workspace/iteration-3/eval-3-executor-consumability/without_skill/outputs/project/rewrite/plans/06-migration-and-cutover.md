# ticketd rewrite — Phase 6: Migration and Cutover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Depends on:** Phases 0-5 complete, all tests green, all verification in
> `../verification/` passing against a full local stack.
> **This phase touches production data. Do not run Task 2 or later against
> real data without a human explicitly signing off first** — this plan can
> get you to "ready to cut over," but the actual cutover of a live internal
> tool with real users is a judgment call about timing (maintenance window,
> rollback plan, who's on call) that this workspace cannot make on its own.
> Treat everything from Task 2 onward as a **runbook to execute together
> with a human**, not something to run unattended.

**Goal:** Get real legacy data into Postgres, verify parity against a
running legacy instance, and decommission the old app.

**Architecture:** N/A — this phase is operational, not architectural.

## Global Constraints

- Nothing here modifies `ticketd/` (the legacy source) — it remains the
  fallback/rollback target until cutover is confirmed successful.
- `ticketd/ops/access.log` is **not** a real 30-day baseline (see
  `../04-TRAFFIC-ANALYSIS.md`) — do not use it alone to decide this is safe
  to cut over without pulling real recent traffic/error data first.

---

### Task 1: Preflight against real data (read-only, safe to run any time)

- [ ] **Step 1: Run the slug-collision check against the real SQLite file**

```bash
python scripts/check_legacy_slug_collisions.py /path/to/production/ticketd.sqlite3
```
If it reports collisions, resolve per `../03-OPEN-QUESTIONS.md` item 2
before continuing — this blocks Task 2 (the new schema's unique index will
reject a straight copy of colliding data).

- [ ] **Step 2: Dry-run the data migration**

```bash
python scripts/migrate_from_sqlite.py /path/to/production/ticketd.sqlite3
```
(no `--commit` flag → dry-run; rolls back). Confirm `users_migrated` and
`tickets_migrated` counts match `SELECT count(*) FROM users` /
`SELECT count(*) FROM tickets` against the real SQLite file.

- [ ] **Step 3: Get the real access/error log** (see
  `../03-OPEN-QUESTIONS.md` item 1) — the log shipped in this workspace is
  a single-hour synthetic sample, not a real 30-day capture. Pull whatever
  the actual production log retention has, and sanity-check that the
  endpoint mix and error rate roughly match what `../04-TRAFFIC-ANALYSIS.md`
  found (61.75% list, etc.) — a large mismatch means this workspace's
  assumptions about read/write ratio may not hold and worker/DB sizing
  should be revisited before cutover.

---

### Task 2: Parallel-run verification (human-supervised)

- [ ] **Step 1: Run legacy and new API side by side** against copies of the
  same data (new API populated via Task 1's dry-run-verified migration,
  then actually committed to a **staging** Postgres, not production).

- [ ] **Step 2: Run `../verification/parity_check.py`** against both,
  covering every endpoint in `../01-CURRENT-BEHAVIOR-CONTRACT.md`. Resolve
  every mismatch before proceeding — see `../verification/VERIFICATION.md`
  for what counts as an acceptable vs. blocking mismatch (timestamp format
  differences are expected and acceptable only if `../03-OPEN-QUESTIONS.md`
  item 3 has been explicitly resolved in favor of changing the format;
  otherwise they're blocking).

- [ ] **Step 3: Run `../verification/smtp_outage_test.py`** against the new
  API with SMTP deliberately blackholed. This is the direct regression test
  for the incident that started this whole project — do not skip it, and do
  not accept a "close enough" result. Confirm close-request p99 latency
  stays flat regardless of SMTP reachability.

---

### Task 3: Cutover (human-supervised, real data, real traffic)

This is a runbook outline, not fully automatable — fill in the blanks with
real environment specifics (deploy tooling, DNS/routing ownership, who has
access) since none of that was available to this workspace (see
`../03-OPEN-QUESTIONS.md` item 8).

- [ ] **Step 1:** Choose a maintenance window (or confirm zero-downtime
  cutover is actually feasible given how traffic gets routed to `ticketd`
  today — unknown from this workspace, see open questions item 7 re: the
  gateway/proxy question).
- [ ] **Step 2:** Run `migrate_from_sqlite.py --commit` against production
  data into production Postgres.
- [ ] **Step 3:** Deploy `ticketd-api` (API + worker process) pointed at
  that Postgres.
- [ ] **Step 4:** Cut traffic over (however routing actually works in this
  org — reverse proxy config change, DNS, load balancer target swap, etc.)
- [ ] **Step 5:** Watch error rates and close-request latency for at least
  one full business day before considering the legacy app safe to stop.
- [ ] **Step 6:** Once confident, stop the legacy Flask process. Do not
  delete `ticketd/` (the source) — keep it as historical reference/rollback
  documentation even after decommissioning the running process.

---

## Definition of done for this phase

- Real data migrated with verified counts and no silent data loss.
- Parity check passes against real (copied) data, not just synthetic test
  fixtures.
- SMTP-outage regression test passes against the new stack.
- Legacy app decommissioned only after a full day of clean operation on the
  new stack.
