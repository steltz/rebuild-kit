-- Verbatim copy of legacy/db/schema.sql (SQLite dialect).
-- Source: legacy/db/schema.sql, pinned tree tree-02fcc10c238482f7672caacb333b91cb3a84e39d0262868efad28f3e524fc0a3.
-- This is the CURRENT schema for citation purposes only. The rewrite's target Postgres schema
-- is P6's job (docs/migration/mapping.md), not this file — do not treat this as the target DDL.

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
-- Note: reset_tokens has no PRIMARY KEY and no UNIQUE constraint on token, verbatim from source
-- (legacy/db/schema.sql:18-22). See docs/domain/reset_token.md for the implication.
