# Hotspots

<!-- Churn caveat: the rewrite-root repo is fresh, so script churn ≈ LOC fallback. Real churn
     signal comes from the pinned legacy repo itself: `git -C ticketd log --oneline` shows
     3 of 4 commits are "hotfix N: reset flow" — the reset flow is the churn hotspot. -->

| file | loc | complexity | churn (legacy git) | why it's hot |
|---|---|---|---|---|
| app/server.py | 125 | 29 | 4/4 commits; 3 reset-flow hotfixes | The whole app: all 7 routes, all branching. Reset flow (lines 80-108) hotfixed 3 times — highest-risk area (PB-002, OQ-002, OQ-006). |
| db/schema.sql | 22 | 0 | initial only | Migration source of truth; `reset_tokens` is a bare table (PB-002); no unique constraint on `slug` (PB-003). |
| app/notify.py | 7 | 0 | initial only | 7 lines that caused the rewrite: synchronous SMTP with 30s timeout inside requests (PB-001). |
| app/util.py | 7 | 0 | initial only | `slugify` — the collision generator (PB-003, OQ-001). |
| app/legacy_import.py | 7 | 0 | initial only | Dead module — zero inbound imports (inventory dep graph) and its own docstring says "Nothing imports this module". do-not-port candidate DNP-002. |

Route-map spot-check (P1 judgment pass): all 7 pattern-detected routes verified against
`ticketd/app/server.py` decorators (lines 27, 40, 58, 67, 80, 98, 111); no dynamically
registered routes exist — the app registers everything via decorators at import time.
Orphan-module check: `app/legacy_import.py` has zero inbound edges — corroborated dead
(docstring + no route references); routed to `docs/do-not-port.md`.

Runtime cross-check (P2): 5xx observed on ticket routes over the 30-day window —
GET /api/tickets 31/1235, POST /api/tickets 12/423, close 5/99, get 3/184
(`usage-weights.json.status_mix`). The code has no explicit 500 path; plausible causes are
SQLite write-lock contention or unhandled exceptions (e.g. CHECK-violating priority,
OQ-007). Cause not evidenced → logged as OQ-008, not asserted.
