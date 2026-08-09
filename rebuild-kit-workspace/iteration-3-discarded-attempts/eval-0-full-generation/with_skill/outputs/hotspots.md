# Hotspots — ticketd

Small app, all files listed (5 source files, 165 LOC total — no sampling needed).

**Note on the script's `churn` column:** it's actually LOC per file, not commit-touch count — a
bug in `inventory.py`'s churn extraction, not a real signal (worth fixing upstream in the skill,
out of scope here). Real churn below is `git log --oneline -- <path> | wc -l` against the pinned
legacy ref (5 commits total: `4788408` initial import, `85e89a2`/`13470b9`/`cf79788` three
same-day "hotfix: reset flow" commits, `1cc1135` "util tweak").

| File | Commits (real churn) | Complexity (script) | Why it's hot |
|---|---|---|---|
| `app/server.py` | 4 | 29 | All 7 routes live here; every PB entry (PB-001 sync email ×2 call sites, PB-002 MD5 token gen, PB-003 slug-collision-free insert, PB-005 UI-depended-on quirks like the 200-on-missing-ticket) traces back to this one file. The three "hotfix: reset flow" commits all touched it — the reset flow has been patched three times since initial import, consistent with PB-002/rate-limit fragility. |
| `app/util.py` | 2 | 0 | Tiny (`slugify`), but it's the direct site of PB-003 — no uniqueness handling at all, and it's been touched twice since initial import. |
| `app/notify.py` | 1 | 0 | Trivial by complexity metric, but it's the literal blocking call PB-001's REPAIR target replaces — small code, large operational blast radius (30s SMTP timeout × every close/reset-request caller). |
| `app/legacy_import.py` | 1 | 0 | Zero inbound references (see `inventory.json.dependency_edges` — nothing points to it); do-not-port candidate, OQ-003. |
| `db/schema.sql` | 1 | 0 | No churn since initial import, but it's the evidence base for PB-002 (`reset_tokens` has no index/TTL/hash-at-rest) and PB-003 (`tickets.slug` has no `UNIQUE` constraint) — the schema itself confirms both defects, not just the code paths. |

## Route map spot-check

All 7 routes in `inventory.json.routes` were confirmed by direct read of `legacy/app/server.py`
— no dynamically registered routes, no blueprints, no missed entrypoints. `detected: pattern` is
accurate for all seven; none needed `detected: manual`.

## Dependency graph check

Two edges (`server.py → notify.py`, `server.py → util.py`) — both real and expected. One orphan:
`app/legacy_import.py` has zero inbound edges and zero route references, matching its own
docstring ("Nothing imports this module"). Flagged as a do-not-port candidate (OQ-003), not
silently dropped, per P1 procedure (orphan modules need "zero inbound imports AND zero route
references" evidence — both hold here).
