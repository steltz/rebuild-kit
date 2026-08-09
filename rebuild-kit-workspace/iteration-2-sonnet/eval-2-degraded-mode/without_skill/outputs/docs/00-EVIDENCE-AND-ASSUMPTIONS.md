# Evidence and Assumptions

This rewrite was generated from a **single source**: the contractor-delivered
`./ticketd` source tree (4 Python files + `db/schema.sql` + a one-line README).
Everything in `./rewrite` and `./docs` is derived from reading that code. No
other evidence was available at generation time.

## Explicitly NOT available

- **Git history** — none was handed over. We cannot see when the two known
  problems were introduced, whether they were ever "fixed and reverted", or
  what the three trailing `# tweak 1/2/3` comments in `server.py` refer to.
- **Access/traffic logs** — we do not know real request volume, which
  endpoints are actually hit in production, or whether `/internal/export/csv`
  (comment: "no caller since [2020]") is truly dead.
- **Production database** — no row counts, no data-quality read, no way to
  test the migration against real rows. Expected available "in a few weeks."
- **Any client/consumer code** — the frontend, scripts, or integrations that
  call this API were not provided. Two comments in `server.py` assert client
  dependencies ("the UI relies on getting everything and filtering
  client-side", "the legacy UI depends on" 200-not-404 for missing tickets),
  but we have no way to confirm or refute those claims independently — we are
  taking the original author's comments at face value, not verifying them.
- **The handover conversation itself** — beyond the two named problems
  (synchronous email sends, MD5 reset tokens), no other prioritization,
  deadline, compliance requirement, or infra constraint was communicated.

## What this means for the deliverable

Because we can't validate assumptions against traffic or a stakeholder before
shipping this, the rewrite in `./rewrite` deliberately:

1. **Fixes only the two named problems** (see
   `02-MIGRATION-PLAN.md` § Fixes Applied). Everything else observed in the
   source is preserved byte-for-byte in behavior, even where it looks like a
   bug, because we have no evidence about who depends on it.
2. **Documents every other oddity found by reading the code** in
   `01-LEGACY-BEHAVIOR-INVENTORY.md` as an open question rather than silently
   "fixing" it. Silent fixes to unconfirmed behavior are how rewrites break
   production in ways nobody can diagnose without the old source to diff
   against.
3. **Does not fabricate numbers.** No SLA, no "handles N req/s", no
   "P99 latency target", no row-count-based sizing appears anywhere in this
   kit. Where a decision would normally be informed by traffic data (e.g.
   pagination defaults, connection pool size, background-worker concurrency),
   we picked a conservative FastAPI/Postgres default and flagged it as
   provisional in `03-OPEN-QUESTIONS-AND-RISK-REGISTER.md`.
4. **Ships without a data migration script.** With no production DB access,
   any migration script we wrote now would be untested against real data and
   would create false confidence. `02-MIGRATION-PLAN.md` specifies the shape
   the migration must take once DB access exists, but the script itself is
   deferred.

## How to "layer the evidence in later"

When git history, access logs, or DB access become available, re-open:

- `01-LEGACY-BEHAVIOR-INVENTORY.md` — confirm or refute each client-dependency
  claim against real logs before changing any preserved behavior.
- `03-OPEN-QUESTIONS-AND-RISK-REGISTER.md` — each row names the evidence that
  would resolve it.
- `02-MIGRATION-PLAN.md` § Data Migration — write and test the actual backfill
  script against a DB snapshot.

None of the code in `./rewrite` needs to be thrown away when that evidence
arrives — it needs its provisional decisions revisited, which is why they're
flagged inline (`# EVIDENCE-NEEDED:`) as well as in these docs.
