-- Reconciliation queries — migration WOs (P8) pass only when these agree between source (SQLite,
-- legacy) and target (Postgres, modern) after a migration run. Run source-side queries against
-- the legacy SQLite file (once one exists — none was supplied to this generator run, so these are
-- unexecuted templates, not verified results) and target-side against the freshly migrated
-- Postgres database; diff the two result sets.
--
-- NOTE on reset_tokens: per docs/migration/mapping.md, the default plan is NOT to migrate any
-- reset_tokens rows (OQ-010, pending ruling). If that ruling changes, add row-count/checksum
-- queries for reset_tokens here matching the pattern below.

-- ==== row counts ====

-- source (sqlite)
SELECT 'tickets' AS table_name, COUNT(*) AS n FROM tickets
UNION ALL
SELECT 'users', COUNT(*) FROM users;

-- target (postgres) — expect exact match; any delta is a migration bug, not "expected drift"
SELECT 'tickets' AS table_name, COUNT(*) AS n FROM tickets
UNION ALL
SELECT 'users', COUNT(*) FROM users;

-- ==== per-column checksums (tickets) ====
-- Order-independent aggregate checksum per column; compare source vs. target for each.
-- SQLite side: no native hash aggregate, use a comparable proxy.
SELECT
  COUNT(*)                                   AS n,
  SUM(LENGTH(title))                         AS title_len_sum,
  SUM(LENGTH(slug))                          AS slug_len_sum,
  COUNT(DISTINCT priority)                   AS priority_distinct,
  COUNT(DISTINCT status)                     AS status_distinct,
  SUM(CASE WHEN assignee_id IS NULL THEN 1 ELSE 0 END) AS assignee_null_count,
  SUM(CASE WHEN closed_at IS NULL THEN 1 ELSE 0 END)   AS closed_at_null_count
FROM tickets;

-- Postgres side: same shape, run against the migrated table, compare field-by-field.
SELECT
  COUNT(*)                                   AS n,
  SUM(LENGTH(title))                         AS title_len_sum,
  SUM(LENGTH(slug))                          AS slug_len_sum,
  COUNT(DISTINCT priority)                   AS priority_distinct,
  COUNT(DISTINCT status)                     AS status_distinct,
  SUM(CASE WHEN assignee_id IS NULL THEN 1 ELSE 0 END) AS assignee_null_count,
  SUM(CASE WHEN closed_at IS NULL THEN 1 ELSE 0 END)   AS closed_at_null_count
FROM tickets;

-- ==== per-column checksums (users) ====
SELECT COUNT(*) AS n, SUM(LENGTH(email)) AS email_len_sum, SUM(LENGTH(name)) AS name_len_sum
FROM users;
-- (same query, target side)

-- ==== stratified sampled field-level diff ====
-- Pull a deterministic sample (every 100th row by id, plus the first/last 20) from BOTH sides and
-- diff field-by-field. This is a manual/scripted step in the twin-boot harness, not a single SQL
-- statement — sketch below, implement in verification/harness/ once real data exists.
--
-- source_sample: SELECT * FROM tickets WHERE id % 100 = 0 OR id <= 20 OR id > (SELECT MAX(id) - 20 FROM tickets) ORDER BY id;
-- target_sample: same query shape against Postgres.
-- Diff every column except id/slug/priority/status (covered by aggregate checks above) with
-- special handling for created_at/closed_at per whichever OQ-006/OQ-009 ruling landed (exact
-- string match if FIXED-naive, or a normalized-to-UTC comparison if REPAIR-timestamptz).

-- ==== assignee_id FK integrity (post-migration) ====
-- Should return 0 on both sides if OQ (orphaned-FK policy in mapping.md) was resolved before
-- migration; a nonzero source-side count with a zero target-side count after enforcement means
-- the migration silently dropped or nulled orphaned references — confirm that was the ratified
-- policy, not a silent side effect.
SELECT COUNT(*) FROM tickets t LEFT JOIN users u ON t.assignee_id = u.id WHERE t.assignee_id IS NOT NULL AND u.id IS NULL;
