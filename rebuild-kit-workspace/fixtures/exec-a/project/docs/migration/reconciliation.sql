-- Reconciliation queries: migration WOs pass only when these agree between source (legacy
-- SQLite dump/export) and target (modern Postgres). Run pre- and post-cutover; the twin-boot
-- harness (verification/harness/) can run these against both local seeded copies during
-- development, not just at real cutover time.

-- ============================== tickets ==============================
-- [R1] Row count parity
SELECT COUNT(*) AS legacy_count FROM tickets;                 -- run against source
-- SELECT COUNT(*) AS modern_count FROM tickets;               -- run against target, compare

-- [R2] Per-column checksum (order-independent) -- catches silent value corruption during
-- transform even when row counts match. Adapt hash fn per engine (md5(), digest(), etc).
SELECT
  COUNT(*) AS n,
  SUM(('x' || substr(md5(id::text || '|' || title || '|' || slug || '|' ||
       coalesce(priority,'') || '|' || status || '|' || coalesce(assignee_id::text,'')), 1, 8))::bit(32)::bigint
  ) AS checksum
FROM tickets;
-- NOTE: excludes created_at/closed_at from the checksum deliberately -- those are the one
-- column pair with an open ASK (OQ-003) about representation change; reconcile them with a
-- separate, looser query (R3) rather than failing the whole-row checksum on a still-open format
-- question.

-- [R3] Timestamp reconciliation (looser: same instant, allowing an OQ-003-dependent representation change)
-- SELECT id, created_at FROM tickets ORDER BY id;   -- source
-- SELECT id, created_at FROM tickets ORDER BY id;   -- target -- compare with tz-aware parsing,
--   not string equality, once OQ-003 is ruled and the actual transform is known.

-- [R4] Slug uniqueness holds post-migration (the actual point of WO-005)
SELECT slug, COUNT(*) FROM tickets GROUP BY slug HAVING COUNT(*) > 1;
-- Expected result on the TARGET side: zero rows, always, once WO-005 ships. On the SOURCE
-- side this is expected to return >0 rows if PB-003 collisions exist -- that's the count
-- census.md probe #26 needs, and the reason this reconciliation query is really a precondition
-- check as much as a post-migration one.

-- [R5] assignee_id FK integrity holds post-migration (Postgres enforces; SQLite may not have -- OQ-005)
SELECT COUNT(*) FROM tickets t LEFT JOIN users u ON t.assignee_id = u.id
WHERE t.assignee_id IS NOT NULL AND u.id IS NULL;
-- Expected zero on target (migration would fail to even create the FK constraint otherwise).
-- On source: whatever census.md probe #12 found -- if nonzero, the mapping.md ASK about
-- orphan policy (nullify vs quarantine) must be resolved before this table can migrate at all.

-- ============================== users ==============================
-- [R6] Row count parity
SELECT COUNT(*) FROM users;

-- [R7] Email uniqueness holds (already enforced both sides -- sanity check, not expected to fail)
SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1;

-- ============================== reset_tokens ==============================
-- reset_tokens is a REDESIGN (PB-002, WO-003), not a translation -- see mapping.md. If the
-- recommended drop-with-log policy is ratified, there is no row-level reconciliation to do:
-- [R8] confirms the drop was total and deliberate, not partial/accidental.
-- SELECT COUNT(*) FROM reset_tokens;   -- target, expect 0 immediately post-cutover under drop-with-log

-- If a human instead ratifies carrying forward *unexpired* tokens (re-issuing new tokens for
-- them rather than dropping), reconciliation is structural, not field-level:
-- [R8-alt] every unexpired legacy token has a corresponding "you have a pending reset" state on target
-- (exact query depends on the ratified carry-forward mechanism -- not written until ASK'd)
