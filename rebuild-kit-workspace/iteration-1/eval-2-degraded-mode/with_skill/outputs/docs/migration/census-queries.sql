-- Dirty-data census (postgres); generated from docs/contracts/ddl.sql
-- Run read-only against prod-shaped data; paste counts into census.md.

-- ==== tickets ====
-- [1] nulls in required column tickets.id
SELECT COUNT(*) FROM tickets WHERE id IS NULL;

-- [2] nulls in required column tickets.title
SELECT COUNT(*) FROM tickets WHERE title IS NULL;

-- [3] encoding anomalies / control chars in tickets.title
SELECT COUNT(*) FROM tickets WHERE title ~ '[\x00-\x08\x0B\x0C\x0E-\x1F]' OR title <> TRIM(title);  -- postgres syntax; adapt per dialect

-- [4] nulls in required column tickets.slug
SELECT COUNT(*) FROM tickets WHERE slug IS NULL;

-- [5] encoding anomalies / control chars in tickets.slug
SELECT COUNT(*) FROM tickets WHERE slug ~ '[\x00-\x08\x0B\x0C\x0E-\x1F]' OR slug <> TRIM(slug);  -- postgres syntax; adapt per dialect

-- [6] encoding anomalies / control chars in tickets.priority
SELECT COUNT(*) FROM tickets WHERE priority ~ '[\x00-\x08\x0B\x0C\x0E-\x1F]' OR priority <> TRIM(priority);  -- postgres syntax; adapt per dialect

-- [7] nulls in required column tickets.status
SELECT COUNT(*) FROM tickets WHERE status IS NULL;

-- [8] encoding anomalies / control chars in tickets.status
SELECT COUNT(*) FROM tickets WHERE status ~ '[\x00-\x08\x0B\x0C\x0E-\x1F]' OR status <> TRIM(status);  -- postgres syntax; adapt per dialect

-- [9] nulls in required column tickets.created_at
SELECT COUNT(*) FROM tickets WHERE created_at IS NULL;

-- [10] timezone-naive / out-of-range datetimes in tickets.created_at
SELECT MIN(created_at), MAX(created_at), COUNT(*) FROM tickets WHERE created_at < '1990-01-01' OR created_at > '2100-01-01';

-- [11] timezone-naive / out-of-range datetimes in tickets.closed_at
SELECT MIN(closed_at), MAX(closed_at), COUNT(*) FROM tickets WHERE closed_at < '1990-01-01' OR closed_at > '2100-01-01';

-- [12] orphaned FK tickets.assignee_id → users.id
SELECT COUNT(*) FROM tickets c LEFT JOIN users p ON c.assignee_id = p.id WHERE c.assignee_id IS NOT NULL AND p.id IS NULL;

-- [13] out-of-range enum values in tickets.priority
SELECT priority, COUNT(*) FROM tickets WHERE priority NOT IN ('low', 'med', 'high') GROUP BY priority;

-- [14] out-of-range enum values in tickets.status
SELECT status, COUNT(*) FROM tickets WHERE status NOT IN ('open', 'closed') GROUP BY status;

-- ==== users ====
-- [15] nulls in required column users.id
SELECT COUNT(*) FROM users WHERE id IS NULL;

-- [16] nulls in required column users.email
SELECT COUNT(*) FROM users WHERE email IS NULL;

-- [17] encoding anomalies / control chars in users.email
SELECT COUNT(*) FROM users WHERE email ~ '[\x00-\x08\x0B\x0C\x0E-\x1F]' OR email <> TRIM(email);  -- postgres syntax; adapt per dialect

-- [18] nulls in required column users.name
SELECT COUNT(*) FROM users WHERE name IS NULL;

-- [19] encoding anomalies / control chars in users.name
SELECT COUNT(*) FROM users WHERE name ~ '[\x00-\x08\x0B\x0C\x0E-\x1F]' OR name <> TRIM(name);  -- postgres syntax; adapt per dialect

-- [20] duplicates under unique intent users(email)
SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*) > 1;

-- ==== reset_tokens ====
-- [21] nulls in required column reset_tokens.email
SELECT COUNT(*) FROM reset_tokens WHERE email IS NULL;

-- [22] encoding anomalies / control chars in reset_tokens.email
SELECT COUNT(*) FROM reset_tokens WHERE email ~ '[\x00-\x08\x0B\x0C\x0E-\x1F]' OR email <> TRIM(email);  -- postgres syntax; adapt per dialect

-- [23] nulls in required column reset_tokens.token
SELECT COUNT(*) FROM reset_tokens WHERE token IS NULL;

-- [24] encoding anomalies / control chars in reset_tokens.token
SELECT COUNT(*) FROM reset_tokens WHERE token ~ '[\x00-\x08\x0B\x0C\x0E-\x1F]' OR token <> TRIM(token);  -- postgres syntax; adapt per dialect

-- [25] nulls in required column reset_tokens.created_ts
SELECT COUNT(*) FROM reset_tokens WHERE created_ts IS NULL;
