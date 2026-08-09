-- T2 seed fixture: deterministic starting state for every replay run (legacy or modern).
-- Applied fresh before each boot so runs are reproducible given the same input set.
-- Schema matches docs/contracts/ddl.sql (verbatim legacy DDL) exactly for the legacy side;
-- the modern/Postgres seed (once WO-003/WO-005 land) is a translated equivalent -- see
-- docs/migration/mapping.md.

CREATE TABLE tickets (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    priority TEXT CHECK (priority IN ('low', 'med', 'high')),
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    assignee_id INTEGER REFERENCES users(id),
    created_at DATETIME NOT NULL,
    closed_at DATETIME
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE reset_tokens (
    email TEXT NOT NULL,
    token TEXT NOT NULL,
    created_ts REAL NOT NULL
);

INSERT INTO users (id, email, name) VALUES (1, 'jdoe@corp.example.com', 'J Doe');

INSERT INTO tickets (id, title, slug, priority, status, assignee_id, created_at, closed_at)
VALUES
  (1, 'Printer on fire', 'printer-on-fire', 'high', 'open', NULL, '2026-07-01T09:00:00', NULL),
  (2, 'Minor typo on login page', 'minor-typo-on-login-page', 'low', 'open', NULL, '2026-07-02T10:00:00', NULL),
  (3, 'Old closed ticket', 'old-closed-ticket', 'med', 'closed', NULL, '2026-06-01T08:00:00', '2026-06-02T08:00:00');

-- A pre-existing reset token, used by the confirm-flow input set (valid + expired variants
-- computed relative to seed time by drive_inputs.py, not hardcoded here, since "30 minutes
-- ago" needs to be relative to run time -- see verification/harness/drive_inputs.py).
