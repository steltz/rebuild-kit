CREATE TABLE tickets (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    slug TEXT NOT NULL, -- unique for NEW slugs (OQ-002 ruling, ED-002): enforced at generation time, not via UNIQUE constraint — pre-ruling duplicate slugs are retained as-is (no migration)
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
