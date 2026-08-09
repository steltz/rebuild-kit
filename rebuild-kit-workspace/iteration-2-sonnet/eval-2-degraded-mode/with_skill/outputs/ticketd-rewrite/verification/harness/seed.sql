-- Seed DB for twin-boot replay. Schema copied from docs/contracts/ddl.sql (verbatim legacy DDL);
-- seed ROWS below are harness fixtures, not real data (no data census evidence exists yet).

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

-- Fixed seed rows: known IDs for deterministic replay traces.
INSERT INTO tickets (id, title, slug, priority, status, assignee_id, created_at, closed_at)
VALUES (100, 'Seeded open ticket', 'seeded-open-ticket', 'low', 'open', NULL, '2026-01-01T00:00:00', NULL);

INSERT INTO tickets (id, title, slug, priority, status, assignee_id, created_at, closed_at)
VALUES (101, 'Seeded closed ticket', 'seeded-closed-ticket', 'high', 'closed', NULL, '2026-01-01T00:00:00', '2026-01-01T01:00:00');
