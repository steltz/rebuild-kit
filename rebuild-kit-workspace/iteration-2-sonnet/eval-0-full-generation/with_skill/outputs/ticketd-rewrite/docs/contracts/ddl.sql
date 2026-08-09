-- Verbatim copy of legacy/db/schema.sql at legacy_ref c28abaddb0dacb789d3b977db736b9d51be02871.
-- SQLite dialect. This is the CURRENT schema for reference only -- the migration TARGET schema
-- (Postgres, with the fixes PB-002/PB-003 require) lives in docs/migration/mapping.md, not here.
-- Note: SQLite does not enforce `REFERENCES` (foreign keys) unless a connection explicitly sets
-- `PRAGMA foreign_keys = ON`; app/server.py never does, so assignee_id -> users.id is very
-- likely declared-but-unenforced today. See docs/open-questions.md OQ-005.

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
