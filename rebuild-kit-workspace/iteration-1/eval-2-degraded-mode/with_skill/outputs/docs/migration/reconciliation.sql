-- Reconciliation checks — migration WO-009 acceptance. All must return expected values.
-- Run after transform, source (SQLite, attached/exported) vs target (Postgres).
-- Convention below: source counts captured into a scratch table `recon_source(metric, val)`
-- by the migration driver before cutover; target queried live. The driver compares.

-- [R1] row counts per carried table (tickets, users; reset_tokens per ratified policy)
SELECT 'tickets_count', COUNT(*) FROM tickets;
SELECT 'users_count', COUNT(*) FROM users;

-- [R2] per-column checksums, tickets (order-independent):
--      source side computes the same aggregate over the exported rows.
SELECT 'tickets_title_checksum',
       md5(string_agg(md5(coalesce(title,'')), '' ORDER BY id)) FROM tickets;
SELECT 'tickets_slug_checksum',
       md5(string_agg(md5(coalesce(slug,'')), '' ORDER BY id)) FROM tickets;
SELECT 'tickets_status_checksum',
       md5(string_agg(status::text, '' ORDER BY id)) FROM tickets;

-- [R3] status/priority distributions must match source exactly (post-policy)
SELECT 'status_dist', status, COUNT(*) FROM tickets GROUP BY status ORDER BY status;
SELECT 'priority_dist', coalesce(priority::text,'NULL'), COUNT(*)
  FROM tickets GROUP BY priority ORDER BY 2;

-- [R4] timestamp conversion spot-audit: stratified sample (every Nth id) of
--      created_at converted back to the ratified source TZ must equal the source string.
--      (Driver renders source values; N chosen so sample >= 100 rows or all rows.)
SELECT 'ts_sample', id, created_at AT TIME ZONE :source_tz
  FROM tickets WHERE id % :stride = 0 ORDER BY id;

-- [R5] referential integrity in target (must be 0 — dangling policy already applied)
SELECT 'dangling_assignees', COUNT(*) FROM tickets t
  LEFT JOIN users u ON t.assignee_id = u.id
  WHERE t.assignee_id IS NOT NULL AND u.id IS NULL;

-- [R6] open tickets have NULL closed_at; closed tickets have NOT NULL closed_at
--      (source may violate the second clause — census will say; policy ASK if so)
SELECT 'open_with_closed_at', COUNT(*) FROM tickets WHERE status='open'  AND closed_at IS NOT NULL;
SELECT 'closed_without_closed_at', COUNT(*) FROM tickets WHERE status='closed' AND closed_at IS NULL;

-- [R7] users email uniqueness survived transform
SELECT 'dup_emails', COUNT(*) FROM (SELECT email FROM users GROUP BY email HAVING COUNT(*)>1) d;

-- [R8] reset_tokens: count carried == count ratified by policy (likely 0; see mapping.md)
SELECT 'reset_tokens_count', COUNT(*) FROM reset_tokens;
