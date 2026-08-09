-- Reconciliation checks — acceptance for WO-007. Run after migrating a copy.
-- Convention: "-- expect:" states the passing value. Source values are computed on the
-- SQLite side with the matching queries in comments.

-- [R1] row counts
SELECT COUNT(*) FROM tickets;   -- expect: == sqlite SELECT COUNT(*) FROM tickets
SELECT COUNT(*) FROM users;     -- expect: == sqlite SELECT COUNT(*) FROM users

-- [R2] id ranges preserved
SELECT MIN(id), MAX(id) FROM tickets;  -- expect: == sqlite MIN/MAX
SELECT MIN(id), MAX(id) FROM users;    -- expect: == sqlite MIN/MAX

-- [R3] per-column checksum: tickets text columns (order-independent)
SELECT md5(string_agg(title  || '|' || slug || '|' || coalesce(priority::text,'') || '|' || status::text, '\n' ORDER BY id)) FROM tickets;
-- expect: == sqlite equivalent:
--   SELECT lower(hex(md5(group_concat(title||'|'||slug||'|'||coalesce(priority,'')||'|'||status, char(10))))) computed via the harness helper (sqlite lacks md5 natively; harness/dump_sqlite.py --checksum)

-- [R4] status distribution preserved
SELECT status, COUNT(*) FROM tickets GROUP BY status ORDER BY status;  -- expect: matches sqlite GROUP BY

-- [R5] priority distribution preserved (including NULLs)
SELECT coalesce(priority::text, '<null>'), COUNT(*) FROM tickets GROUP BY 1 ORDER BY 1;  -- expect: matches sqlite

-- [R6] timestamp round-trip (blocked by OQ-005: run once TZ policy is ruled)
-- For a stratified sample of 100 ids: converting target created_at back to the ruled source
-- TZ and formatting as ISO must reproduce the source string exactly.
-- expect: 100/100 matches

-- [R7] invariant I4 dirt did not grow: closed tickets without closed_at
SELECT COUNT(*) FROM tickets WHERE status = 'closed' AND closed_at IS NULL;
-- expect: == the count observed in the source census (policy may repair to 0; ratify in mapping.md)

-- [R8] FK integrity after migration (SQLite never enforced it)
SELECT COUNT(*) FROM tickets t LEFT JOIN users u ON t.assignee_id = u.id
WHERE t.assignee_id IS NOT NULL AND u.id IS NULL;  -- expect: 0 (per ratified orphan policy)

-- [R9] reset_tokens not migrated (mapping.md policy, pending ratification)
SELECT COUNT(*) FROM reset_tokens;  -- expect: 0 at cutover

-- [R10] user emails preserved exactly
SELECT md5(string_agg(email || '|' || name, '\n' ORDER BY id)) FROM users;  -- expect: == sqlite equivalent via harness helper
