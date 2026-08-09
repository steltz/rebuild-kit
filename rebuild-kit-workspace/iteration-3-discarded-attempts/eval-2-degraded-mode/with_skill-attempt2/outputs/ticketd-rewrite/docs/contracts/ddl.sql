-- Verbatim dump of legacy/db/schema.sql (sqlite dialect), pinned at legacy_ref
-- tree-02fcc10c238482f7672caacb333b91cb3a84e39d0262868efad28f3e524fc0a3.
-- This is CURRENT-STATE schema, not the migration target — see docs/migration/ (P6) for the
-- Postgres target DDL.

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
