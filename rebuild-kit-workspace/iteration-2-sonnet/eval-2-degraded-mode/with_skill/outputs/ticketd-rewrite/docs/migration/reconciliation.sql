-- Reconciliation checks for the (future) migration WO. Run against SQLite (source) and
-- Postgres (target) after a migration run; a migration WO passes only when these agree.
-- Drafted from DDL alone (P6, degraded mode) — no real data to test these against yet.

-- ==== Row counts ====
-- SQLite:   SELECT COUNT(*) FROM tickets;
-- Postgres: SELECT COUNT(*) FROM tickets;
-- (repeat for users, reset_tokens — reset_tokens counts will legitimately differ if the
--  drop-with-log policy for expired tokens, proposed in mapping.md, is ratified — that's an
--  EXPECTED divergence, document it in verification/replay/expected-divergences.yaml once ruled)

-- ==== Per-column checksum (tickets) ====
-- SQLite:   SELECT id, title, slug, priority, status, created_at, closed_at FROM tickets ORDER BY id;
-- Postgres: SELECT id, title, slug, priority, status, created_at, closed_at FROM tickets ORDER BY id;
-- Compare row-by-row after normalizing created_at/closed_at per the OQ-001 ruling (naive-local
-- vs UTC — the normalization rule itself depends on that ruling, so this check cannot be
-- finalized until OQ-001 is resolved).

-- ==== Stratified sample field-level diff ====
-- Sample N=100 (or 100% if total rows < 500) tickets per status value; diff every field.
-- SELECT * FROM tickets WHERE status = 'open' ORDER BY RANDOM() LIMIT 100;
-- SELECT * FROM tickets WHERE status = 'closed' ORDER BY RANDOM() LIMIT 100;

-- ==== Orphan check post-migration (tickets.assignee_id -> users.id) ====
-- Only meaningful once OQ-003 is ruled and the FK enforcement policy in mapping.md is settled.
-- SELECT COUNT(*) FROM tickets t LEFT JOIN users u ON t.assignee_id = u.id
--   WHERE t.assignee_id IS NOT NULL AND u.id IS NULL;
-- Expected: 0 in Postgres if FK enforcement is turned on during migration; unenforced parity
-- check against SQLite's count (query [12] in census-queries.sql) if not.

-- ==== reset_tokens row-count delta ====
-- Expected: postgres_count <= sqlite_count, with the delta explained entirely by the
-- drop-with-log policy (rows older than 30 min at migration time) IF that policy is ratified.
-- If unratified, expected delta is 0 (straight copy).
