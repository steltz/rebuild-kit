# Hotspots

Small app, all files listed (5 source files, 165 LOC total). Git history is thin — 1 initial
import + 3 one-line "hotfix" commits to `server.py` + 1 one-line tweak to `util.py`, all same-day
— so the churn column is dominated by cumulative added-line counts, not real repeated-edit
signal; treat it as roughly `≈ loc` and rely on complexity + route count for prioritization
instead. No file here has enough history to say anything about *how often it breaks*, only what's
in it today.

| file | loc | complexity | churn | why it's hot |
|---|---|---|---|---|
| app/server.py | 122 | 29 | 122 | All 7 routes, all business logic, all three problem-brief defects (PB-001 sync SMTP, PB-002 MD5 tokens, PB-003 slug collisions) live here. Highest complexity by a wide margin (29 vs. 0 elsewhere) because every endpoint's branching (rate limit, token expiry, priority coercion, missing-ticket handling) is inline in one route function each — no shared validation/service layer to isolate risk. This is the file P4/P8 must decompose most carefully; almost every WO cites it. |
| db/schema.sql | 22 | 0 | 22 | Small (3 tables) but load-bearing for the migration: `reset_tokens` has no PK/index/expiry mechanism (PB-002), `tickets.assignee_id` references a `users` table nothing in `server.py` ever populates or queries (dead FK — no route touches `users` at all, worth a P6 census check), and `priority`/`status` are DB-level CHECK-constrained enums that the app-level code duplicates logic around (`server.py:47-49`). |
| app/legacy_import.py | 7 | 0 | 7 | Zero complexity, zero inbound references — confirmed dead code (do-not-port.md), not actually "hot" by risk, listed here only because it's one of the 5 files that exist. |
| app/notify.py | 7 | 0 | 7 | Tiny file, but it's the entire PB-001 blast radius: one function, one blocking `smtplib.SMTP(...)` call with a 30s timeout, called synchronously from two call sites in `server.py` (ticket close, reset request). Fixing PB-001 means changing how this function is invoked, not necessarily what's inside it. |
| app/util.py | 7 | 0 | 7 | One function (`slugify`), zero complexity, but it's the entire surface area of PB-003 — the collision is a one-line consequence of `slugify` having no uniqueness awareness and its caller (`server.py:50-55`) never checking for one. |
