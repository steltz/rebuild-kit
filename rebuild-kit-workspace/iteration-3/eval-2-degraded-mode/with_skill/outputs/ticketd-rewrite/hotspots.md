# Hotspots

<!-- No git history on the legacy tree (contractor handover) → churn is unavailable.
     Complexity-only ranking. Small app: all 5 source files are listed, not a top-N sample. -->

Route map spot-checked by hand against `legacy/app/server.py` in full (P0 read) — all 7 routes
detected by the pattern scanner match; no dynamically-registered routes found; nothing to add
as `detected: manual`.

| file | loc | complexity | churn | why it's hot |
|---|---|---|---|---|
| app/server.py | 122 | 29 | — (no git history) | The entire route surface (7 endpoints) lives in one file: ticket CRUD, the close+notify flow (PB-001), and the full auth-reset flow (PB-002, rate limiting, non-disclosure semantics). Highest complexity by a wide margin and the only file with externally-observable behavior — every WO touches it. |
| app/notify.py | 7 | 0 | — (no git history) | Trivially small but load-bearing for PB-001: its own docstring documents the blocking behavior ("Blocks the request thread; ~2s typical, 30s on provider trouble"). Low complexity, high risk concentration — the whole defect is one function. |
| app/util.py | 7 | 0 | — (no git history) | `slugify()` has a documented collision behavior (two distinct titles can produce the same slug) that's evidenced in-code but not raised by the task owner — carried forward as FIXED unless a future ruling says otherwise. |
| db/schema.sql | 22 | 0 | — (no git history) | Only DDL source available; no migrations directory, so this is the sole schema evidence. `users`/`assignee_id` are defined but never referenced by any route (see `docs/open-questions.md#OQ-004`). |
| app/legacy_import.py | 7 | 0 | — (no git history) | Zero inbound imports, zero route references — orphan by both static checks in P1. Candidate do-not-port (`docs/do-not-port.md#DNP-001`), pending `docs/open-questions.md#OQ-003` since no access-log evidence exists to fully confirm zero real-world use. |

## Orphan modules

- `app/legacy_import.py` — 0 inbound dependency edges (confirmed by `inventory.json`), 0 routes.
  Matches its own docstring ("Nothing imports this module"). See DNP-001.

No other orphans; `app/notify.py` and `app/util.py` are both imported by `app/server.py` per
`inventory.json.dependency_edges`.
