-- Verbatim copy of legacy/db/schema.sql (SQLite dialect) — the CURRENT schema, byte-for-byte.
-- P5 output: freeze-in-place. The Postgres TARGET schema is P6's job (docs/migration/mapping.md).
-- Note: reset_tokens has no primary key in the current schema (see docs/domain/reset-token.md).

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
