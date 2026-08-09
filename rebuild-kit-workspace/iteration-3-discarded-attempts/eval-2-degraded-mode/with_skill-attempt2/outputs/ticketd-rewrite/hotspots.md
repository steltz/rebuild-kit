# Hotspots

<!-- P1. legacy/ has no git history (confirmed at intake), so true churn is unavailable — the
     "churn" field the inventory script can otherwise emit is a line-count fallback, not real
     change frequency, and is omitted below (—) per Degraded Mode rules in SKILL.md. Small app:
     all 5 legacy files are listed (5 files total) rather than a top-N cut. -->

Route map spot-checked against `legacy/app/server.py` by direct reading (not just the pattern
detector): all 7 routes the script found match; no dynamically-registered routes were missed.
`app/legacy_import.py` is confirmed an orphan (0 inbound dependency edges, 0 outbound routes) —
tracked in `docs/do-not-port.md` / OQ-006, not a detection gap.

| file | loc | complexity | churn | why it's hot |
|---|---|---|---|---|
| app/server.py | 122 | 29 | — | All 7 routes live here in one file: ticket CRUD-lite, auth/reset (PB-002), and the synchronous email call sites (PB-001, lines 76 & 94). Every WO in this rewrite touches this file — it's the entire application surface, and highest-risk by a wide margin. |
| app/legacy_import.py | 7 | 0 | — | Not hot by complexity; flagged because it's confirmed dead code (0 inbound imports, 0 route references) — see `docs/do-not-port.md`, OQ-006. |
| app/notify.py | 7 | 0 | — | Trivially small but structurally central to PB-001 — the entire "sync SMTP blocks the request" defect lives in this one function, called from two sites in `server.py`. Risk is behavioral (timeout/availability), not complexity. |
| app/util.py | 7 | 0 | — | `slugify()` — small; `server.py:6` comments confirm slug collisions are a known, accepted behavior (two tickets with different titles can share a slug). No PB backing to change it; preserved FIXED. |
| db/schema.sql | 22 | 0 | — | Source of truth for the Postgres DDL migration (P5/P6). `reset_tokens` has no primary key and no index on `token` or `email` — a full-table scan backs the rate-limit query (`server.py:85-87`) and the token lookup (`server.py:101-102`). Not named in the problem brief, so not a REPAIR target, but relevant to Postgres schema design (FREE) — noted in `docs/contracts/ddl.sql`. |

## Risk feed-forward to P8

`server.py` is the dominant risk driver for essentially every work order (it's the only
application-logic file). Per-WO risk scoring in P8 differentiates by *behavior area* (ticket
CRUD vs. auth/reset) rather than by file, since file-level granularity doesn't discriminate here.
