-- PROPOSED PostgreSQL target schema (WO-001 creates it; WO-007 migrates into it).
-- FREE choices are marked; ASK items must be ruled before the affected DDL is final.

CREATE TYPE ticket_priority AS ENUM ('low', 'med', 'high');  -- FREE: enum vs CHECK; values FIXED (glossary: 'med' spelling is load-bearing)
CREATE TYPE ticket_status  AS ENUM ('open', 'closed');

CREATE TABLE users (
    id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name  TEXT NOT NULL
);

CREATE TABLE tickets (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title       TEXT NOT NULL,
    slug        TEXT NOT NULL,          -- ASK OQ-001: add UNIQUE? suffixing? unchanged?
    priority    ticket_priority,        -- nullable, matching legacy (rows can have NULL priority via direct DB writes; API always sets it)
    status      ticket_status NOT NULL,
    assignee_id BIGINT REFERENCES users(id),
    created_at  timestamptz NOT NULL,   -- ASK OQ-005: source TZ for conversion
    closed_at   timestamptz
);
CREATE INDEX tickets_status_created_idx ON tickets (status, created_at DESC);  -- FREE: serves list route

-- PB-002 repair: replaces legacy reset_tokens (which is NOT migrated — mapping.md)
CREATE TABLE reset_tokens (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email      TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,    -- SHA-256 of a >=128-bit random token; cleartext never stored (NFR-3)
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL     -- created_at + 30 min (RESET_WINDOW_MIN stays 30, server.py:16)
);
CREATE INDEX reset_tokens_email_created_idx ON reset_tokens (email, created_at);  -- serves rate-limit count

-- PB-001 repair, OQ-004 default mechanism (FREE): transactional outbox
CREATE TABLE mail_outbox (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    mail_from  TEXT NOT NULL,
    mail_to    TEXT NOT NULL,
    body       TEXT NOT NULL,           -- headerless raw body, mail-message.schema.json
    created_at timestamptz NOT NULL DEFAULT now(),
    sent_at    timestamptz              -- NULL = pending; worker delivers at-least-once
);
