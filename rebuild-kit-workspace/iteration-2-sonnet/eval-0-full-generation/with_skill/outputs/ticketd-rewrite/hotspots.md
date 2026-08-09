# Hotspots

<!-- Small app: all 5 legacy source files listed (not just top-N). Churn column from the
     inventory script is loc-scaled; the actually meaningful churn signal is commit count per
     file, added by hand below from `git -C ticketd log --stat` (5 commits total). -->

| file | loc | complexity | commits touching it | why it's hot |
|---|---|---|---|---|
| app/server.py | 125 | 29 | 4 (initial + 3 "hotfix N: reset flow") | Highest complexity file by far (all 7 routes + all business logic live here — no layering). All three post-initial hotfixes targeted the auth/reset flow specifically (`app/server.py:80-108`), i.e. the exact code path holding PB-002 (MD5 tokens) — three unlabeled point-fixes on a flow nobody has properly redesigned is itself evidence the area is fragile, not just risky on paper. Also the site of PB-001's two synchronous `send_mail` calls (lines 76, 94). Highest-risk file for P8 WO scoring. |
| db/schema.sql | 22 | 0 | 1 (initial only) | Small, static, but load-bearing: `reset_tokens` (PB-002) has no PK/index/expiry column, and `tickets.slug` (PB-003) has no UNIQUE constraint — both root causes are schema-level, not just app-code bugs, and migration WOs (P6) must decide the new DDL here. |
| app/util.py | 8 | 0 | 2 (initial + "util tweak") | Tiny, but `slugify()` is PB-003's entire mechanism — the collision behavior is a 3-line function with a comment openly acknowledging the bug. The "util tweak" commit only added a trailing comment (`# note` x2), not a behavior change — confirmed by diff, not just the commit message. |
| app/notify.py | 7 | 0 | 1 (initial only) | Never touched again after initial import despite being the direct cause of the June outage (PB-001) — the fix always happened (or was attempted) at the call sites in server.py, never here. Docstring self-reports the failure mode ("Blocks the request thread; ~2s typical, 30s on provider trouble"). |
| app/legacy_import.py | 7 | 0 | 1 (initial only) | Zero inbound references anywhere in the tree (confirmed: not in `inventory.json.dependency_edges`, not imported by `app/server.py`, no route wires it up) and its own docstring says "Nothing imports this module." Do-not-port candidate — see `docs/do-not-port.md`. |
