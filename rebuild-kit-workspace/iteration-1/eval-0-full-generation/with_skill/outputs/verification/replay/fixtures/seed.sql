-- Canonical twin-boot seed. Identical logical content must exist in BOTH trees before a
-- replay run: SQLite via this file (run-legacy.sh), Postgres via seed-modern.sql mapping
-- (WO-001 creates it from this file + target-schema.sql). Deterministic by construction.

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

INSERT INTO users (id, email, name) VALUES
  (1, 'jdoe@corp.example.com', 'Jane Doe');

INSERT INTO tickets (id, title, slug, priority, status, assignee_id, created_at, closed_at) VALUES
  (1, 'Printer on 3rd floor jams', 'printer-on-3rd-floor-jams', 'med',  'open',   NULL, '2026-07-01T09:15:00.000001', NULL),
  (2, 'VPN drops every hour',      'vpn-drops-every-hour',      'high', 'closed', NULL, '2026-07-02T14:30:00.000001', '2026-07-03T10:00:00.000001'),
  (3, 'Replace keyboard',          'replace-keyboard',          'low',  'open',   NULL, '2026-07-03T08:00:00.000001', NULL);
