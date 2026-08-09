-- ticketd rewrite target schema (Postgres)
--
-- Derived from ../../ticketd/db/schema.sql (SQLite). Structural changes from
-- the legacy schema are called out inline with EVIDENCE-NEEDED / rationale
-- comments. Everything else is a direct, faithful port.
--
-- This file is the authoritative "migration 0001" baseline. Treat it as the
-- output of `alembic revision --autogenerate` for a fresh database — once a
-- real migration tool is wired up (see docs/02-MIGRATION-PLAN.md), this SQL
-- should become that tool's initial revision rather than being hand-run.

CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL
);

CREATE TABLE tickets (
    id            BIGSERIAL PRIMARY KEY,
    title         TEXT NOT NULL,
    slug          TEXT NOT NULL,
    -- CHECK constraints ported verbatim from the legacy schema.
    priority      TEXT NOT NULL DEFAULT 'med' CHECK (priority IN ('low', 'med', 'high')),
    status        TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    assignee_id   BIGINT REFERENCES users(id),
    -- CHANGE: TIMESTAMPTZ instead of the legacy naive-local-time DATETIME
    -- (ticketd/app/server.py:52 stores datetime.now(), no tz). This is an
    -- architectural default for the new stack, not a response to a named
    -- problem — flagged in docs/01-LEGACY-BEHAVIOR-INVENTORY.md and
    -- docs/03-OPEN-QUESTIONS-AND-RISK-REGISTER.md. The JSON contract
    -- (ISO-8601 string) is unchanged; only the stored precision/tz gains
    -- meaning.
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at     TIMESTAMPTZ
);

-- EVIDENCE-NEEDED: legacy slugify() can collide (see behavior inventory) and
-- the legacy schema has no uniqueness constraint on slug. We have NOT added
-- one here — doing so would reject writes the legacy system silently
-- accepted, and we have no evidence about how often that happens today.
-- Revisit once production data is available (docs/02-MIGRATION-PLAN.md).
CREATE INDEX ix_tickets_status_created_at ON tickets (status, created_at DESC);
CREATE INDEX ix_tickets_slug ON tickets (slug);

-- CHANGE (fixes Known Problem #2 — MD5 reset tokens):
-- The legacy `reset_tokens` table stored the raw token in plaintext
-- (ticketd/db/schema.sql). The rewrite stores only a SHA-256 hash of a
-- cryptographically random token (see app/services/tokens.py); the plaintext
-- token exists only in the outbound email and is never persisted. This is a
-- storage-layer change only — the external contract (a token string appears
-- in the reset email, is POSTed back to /api/auth/reset/confirm) is
-- unchanged.
CREATE TABLE reset_tokens (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT NOT NULL,
    token_hash  TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    used_at     TIMESTAMPTZ
);

CREATE INDEX ix_reset_tokens_email_created_at ON reset_tokens (email, created_at DESC);

-- NEW (fixes Known Problem #1 — synchronous email in-request):
-- Transactional outbox. Requests that need to notify someone write a row
-- here in the SAME transaction as their primary write (e.g. closing a
-- ticket), then return immediately. A separate worker process
-- (app/worker.py) polls this table and does the actual SMTP send outside
-- the request path. See docs/02-MIGRATION-PLAN.md for why this pattern was
-- chosen over an in-process background task or an external queue.
CREATE TABLE notification_outbox (
    id            BIGSERIAL PRIMARY KEY,
    to_email      TEXT NOT NULL,
    subject       TEXT NOT NULL,
    body          TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at       TIMESTAMPTZ,
    attempts      INTEGER NOT NULL DEFAULT 0,
    last_error    TEXT
);

CREATE INDEX ix_notification_outbox_unsent ON notification_outbox (created_at) WHERE sent_at IS NULL;
