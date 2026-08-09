# ADR-004: Postgres schema shape and timestamp policy

Status: accepted, with one open input (server timezone). Date: 2026-08-08.

## Schema shape (`../sql/001_initial.sql`)

- Legacy tables ported 1:1 (`tickets`, `users`, `reset_tokens`) plus new
  `outbox_emails` (ADR-001).
- `priority`/`status` stay **TEXT + CHECK**, not Postgres ENUMs — identical constraint
  semantics to legacy, and migration of any out-of-range legacy values (intake C2) is
  a data conversation, not a type migration.
- `slug` stays non-unique (Q7). `users` and `assignee_id` are ported even though the
  code never touches them (Q2) — dropping schema that an unknown external writer may
  use is exactly the mistake this workspace exists to avoid.
- `reset_tokens` gains `token_hash` (ADR-002) and an index; still no FK to users
  (legacy minted tokens for arbitrary emails, preserved).
- `id`s become `BIGINT GENERATED ALWAYS AS IDENTITY`; migration preserves legacy ids
  and resets the sequence.

## Timestamps

- Storage: `timestamptz` (UTC internally). Epoch-float `created_ts` on reset tokens
  becomes `timestamptz` too.
- Serialization: legacy clients receive naive local-time ISO strings today, so the API
  serializes timestamps as naive ISO in the configured `LEGACY_TZ` (compat with Q-list
  in ADR-003).
- **Open input `[U]`:** the legacy server's timezone (intake D3/C4). `LEGACY_TZ`
  defaults to `UTC` as a placeholder; migration MUST NOT run for real until it's
  confirmed — a wrong value skews every historical timestamp by hours.

## Consciously deferred

- Auth (Q1): none added, matching legacy; revisit after D3 clarifies network posture.
- Pagination (Q4): deferred pending C1/A3.
- `updated_at`/audit columns, soft deletes: not in legacy, not added — the rewrite's
  first job is parity, not features.
