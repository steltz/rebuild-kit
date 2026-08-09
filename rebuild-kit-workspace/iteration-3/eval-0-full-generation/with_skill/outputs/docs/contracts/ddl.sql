-- Verbatim copy of ticketd/db/schema.sql at legacy_ref 1cc113597ea87990e731f02190fc6999e42e7cd8.
-- This is the CURRENT (legacy) schema, frozen for contract reference — it is not the migration
-- target. The target Postgres DDL lives in docs/migration/ (P6), derived from this file plus the
-- domain entity docs (docs/domain/) and the fidelity decisions in the work orders.
-- SQLite dialect: no PRIMARY KEY/UNIQUE/index exists on reset_tokens (see docs/domain/reset_token.md);
-- SQLite does not enforce FOREIGN KEY constraints by default and no PRAGMA enabling it appears
-- anywhere in ticketd/app/server.py, so tickets.assignee_id -> users.id is declared but unenforced.

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
