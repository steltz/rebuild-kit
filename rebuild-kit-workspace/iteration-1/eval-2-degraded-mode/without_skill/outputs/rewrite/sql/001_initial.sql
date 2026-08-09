-- ticketd rewrite: initial Postgres schema.
-- Shape decisions: decisions/ADR-004-postgres-schema-and-time.md
-- Legacy source of truth: ticketd/db/schema.sql

BEGIN;

CREATE TABLE users (
    id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name  TEXT NOT NULL
);
-- Q2: no code path in legacy ticketd touches this table; ported anyway because an
-- external writer may exist (see inventory/dead-code-and-unknowns.md).

CREATE TABLE tickets (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title       TEXT NOT NULL,
    slug        TEXT NOT NULL,          -- deliberately NOT unique (Q7)
    priority    TEXT CHECK (priority IN ('low', 'med', 'high')),  -- nullable, like legacy
    status      TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    assignee_id BIGINT REFERENCES users(id),   -- never set by app code (Q2)
    created_at  TIMESTAMPTZ NOT NULL,
    closed_at   TIMESTAMPTZ
);

CREATE INDEX tickets_status_created_idx ON tickets (status, created_at DESC);
CREATE INDEX tickets_created_idx ON tickets (created_at DESC);

CREATE TABLE reset_tokens (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email      TEXT NOT NULL,
    token_hash TEXT NOT NULL,           -- sha256 hex of the token (ADR-002); plaintext never stored
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX reset_tokens_hash_idx  ON reset_tokens (token_hash);
CREATE INDEX reset_tokens_email_idx ON reset_tokens (email, created_at);

-- Transactional email outbox (ADR-001).
CREATE TABLE outbox_emails (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recipient    TEXT NOT NULL,
    body         TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at      TIMESTAMPTZ,
    attempts     INTEGER NOT NULL DEFAULT 0,
    last_error   TEXT
);

CREATE INDEX outbox_pending_idx ON outbox_emails (created_at) WHERE sent_at IS NULL;

COMMIT;
