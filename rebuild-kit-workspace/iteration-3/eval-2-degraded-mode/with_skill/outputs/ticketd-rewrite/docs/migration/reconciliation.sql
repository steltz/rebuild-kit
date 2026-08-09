-- Reconciliation queries — run source (SQLite, legacy) vs target (Postgres, modern) after any
-- migration WO's dry run, per docs/migration/mapping.md. These are the acceptance oracle for
-- migration WOs (schema.md: "Migration WOs pass only when reconciliation checks do").
-- UNRUN this pass — no data access available (see census.md). Shipped as the concrete check a
-- migration WO must pass, not as evidence of a completed migration.

-- ==== Row counts ====
-- source (sqlite)
SELECT 'tickets' AS table_name, COUNT(*) AS row_count FROM tickets
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'reset_tokens', COUNT(*) FROM reset_tokens;

-- target (postgres) — same shape, run against modern DB and diff totals
SELECT 'tickets' AS table_name, COUNT(*) AS row_count FROM tickets
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'reset_tokens', COUNT(*) FROM reset_tokens;
-- NOTE: reset_tokens counts are expected to diverge under the drop-with-log migration policy
-- proposed in mapping.md (pending ratification) — if that policy is adopted, target reset_tokens
-- count should be 0 immediately post-migration, not equal to source.

-- ==== Per-table checksums (order-independent, column-wise) ====
-- tickets: checksum over stable, migrated columns (excludes columns under an open ASK — see
-- mapping.md for created_at/closed_at timezone handling; re-add once ratified).
SELECT
  COUNT(*) AS n,
  SUM(id) AS id_sum,
  COUNT(DISTINCT slug) AS distinct_slugs,          -- expect < COUNT(*) if collisions exist, by design (docs/domain/ticket.md)
  SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) AS closed_count,
  SUM(CASE WHEN priority = 'low' THEN 1 ELSE 0 END) AS low_count,
  SUM(CASE WHEN priority = 'med' THEN 1 ELSE 0 END) AS med_count,
  SUM(CASE WHEN priority = 'high' THEN 1 ELSE 0 END) AS high_count
FROM tickets;
-- Run identically against modern; every value must match exactly. distinct_slugs matching is a
-- migration-fidelity check, NOT a claim that slugs are unique (they are not, see mapping.md).

-- users
SELECT COUNT(*) AS n, COUNT(DISTINCT email) AS distinct_emails FROM users;
-- distinct_emails should equal n given the source UNIQUE constraint (census #20 should confirm
-- no pre-existing violations bypassed it).

-- ==== Stratified sample field-level diff ====
-- Pull N=50 tickets stratified by status (open/closed) from source, join the same ids from
-- target, diff every migrated column. Left as a parameterized query for the migration WO to
-- fill in with an actual sampling seed once real data exists — no sampling is meaningful over
-- an empty/synthetic dataset.
-- SELECT id, title, slug, priority, status FROM tickets WHERE status = 'open' ORDER BY RANDOM() LIMIT 25;
-- SELECT id, title, slug, priority, status FROM tickets WHERE status = 'closed' ORDER BY RANDOM() LIMIT 25;

-- ==== Orphaned FK check (post-migration) ====
SELECT COUNT(*) FROM tickets t LEFT JOIN users u ON t.assignee_id = u.id
WHERE t.assignee_id IS NOT NULL AND u.id IS NULL;
-- Must be 0 in both source and target (target should be a strict subset of source's orphan
-- count at worst, never a superset — migration must not introduce new orphans).
