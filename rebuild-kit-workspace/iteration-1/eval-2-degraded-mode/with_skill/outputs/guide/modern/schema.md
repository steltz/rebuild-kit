# schema (designed-not-built)

Status: initial DDL lands with WO-001 (Alembic). tickets/users carried with modern types
(identity PKs, timestamptz UTC, enums, ENFORCED assignee FK); reset_tokens restructured to
hashed tokens (ED-003). Full mapping + dirty-data policies: docs/migration/mapping.md —
every policy an ASK until census (OQ-INT-2) and owner sign-off.
