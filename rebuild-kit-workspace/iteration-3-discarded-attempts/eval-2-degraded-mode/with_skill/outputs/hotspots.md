# Hotspots

<!-- Small app, all files listed — complexity-only ranking. -->

**Degraded mode: no churn data.** The legacy app was handed over with no git history (see
`rebuild.json.legacy_pin_method: unversioned-snapshot`). Real per-file churn is unavailable;
ranking below is complexity + route-count only.

**Route map spot-check (P1 step 1):** all 7 routes in `inventory.json` were confirmed by direct
reading of `ticketd-nohistory/app/server.py` — Flask's `@app.route` decorator pattern is the only
registration mechanism used, no dynamic/programmatic route registration exists. Nothing to add.

| file | loc | complexity | churn | why it's hot |
|---|---|---|---|---|
| app/server.py | 122 | 29 | — (no history) | Entire HTTP surface, all business logic, and both known defects (PB-001, PB-002) live in one file — every WO except a pure-migration one touches it. |
| app/legacy_import.py | 7 | 0 | — (no history) | **Orphan module.** Zero inbound imports, zero route references, own docstring says "nothing imports this module." Meets the do-not-port evidence bar; seeded there. |
| app/notify.py | 7 | 0 | — (no history) | Tiny, but it's the exact site of PB-001 (synchronous SMTP, 30s timeout) — small file, outsized behavioral risk. |
| app/util.py | 7 | 0 | — (no history) | `slugify()` has a documented collision risk in its own comment (`app/util.py:5`) — not user-reported, so it stays FIXED, but flagged for P9 as a spec item rather than silently ported. |
| db/schema.sql | 22 | — | — (no history) | Not code-complex, but the entire data model (3 tables) — every WO's contract traces back here. |

## Orphan module disposition

`app/legacy_import.py` is a one-off CSV importer from "the 2019 spreadsheet era" (its own
docstring). No route calls it, no other module imports it, and it isn't referenced from
`README.md`'s single run instruction (`python -m app.server`). Seeded to `docs/do-not-port.md`
with this evidence; if the human knows of an out-of-band invocation (a cron job, a manual
migration step still run today), that overrides this and should come back as a PB entry or a
ruling, not a silent restoration.
