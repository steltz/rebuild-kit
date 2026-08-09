# Draft spec — tickets/create  (`POST /api/tickets`)

Usage weight 0.2115. Perf p50 24ms / p95 66ms / p99 100ms.

| id | claim | fidelity | confidence | evidence |
|---|---|---|---|---|
| TC-1 | Body is JSON; non-JSON or absent body is tolerated (`silent=True`) and treated as `{}` → 422 title_required, never a 400 parse error | FIXED | cited+traced | `ticketd/app/server.py:42`; trace `tickets-create-004` |
| TC-2 | `title` required after `.strip()`; missing/blank → 422 `{"error":"title_required"}` | FIXED | cited+traced | `ticketd/app/server.py:43-45`; traces `tickets-create-004/005` |
| TC-3 | Stored title is the **stripped** version | FIXED | cited | `ticketd/app/server.py:43` (strip happens before insert via `title` var, `:52`) |
| TC-4 | `priority` accepted as int or string; `1/2/3` (as string OR number — `str()` first) map to low/med/high; absent → "med"; both client styles must keep working | FIXED | cited+traced | `ticketd/app/server.py:46-49` (comment); traces `tickets-create-002/003/009` |
| TC-5 | Any other priority value passes through raw → DB CHECK violation → 500 | ASK (OQ-007) | cited+traced | `ticketd/app/server.py:47-49` + `ticketd/db/schema.sql:5`; trace `ask-priority-500` (edge-ask set) |
| TC-6 | `slug = slugify(title)`: lowercase, non-alphanumerics collapsed to `-`, trimmed of `-`, truncated to 64 chars | REPAIR (PB-003) — target pending OQ-001; until ruled, exact legacy behavior | cited+traced | `ticketd/app/util.py:4-6`; traces `tickets-create-006/007/008` |
| TC-7 | Slug collisions are allowed (no unique constraint) | REPAIR (PB-003, same ruling) | cited+traced | `ticketd/db/schema.sql:4`; traces `tickets-create-006/007` |
| TC-8 | New tickets: `status='open'`, `created_at=datetime.now().isoformat()` (naive local) | FIXED (timestamp normalized in L3; TZ policy OQ-005) | cited+traced | `ticketd/app/server.py:50-52`; trace `tickets-create-001` |
| TC-9 | Response 201 `{"id": <rowid>, "slug": "<slug>"}` — note: slug recomputed on the **unstripped** original? No: computed from stripped `title` both times | FIXED | cited+traced | `ticketd/app/server.py:52,55` (`slugify(title)` twice, same input); trace `tickets-create-001`. Log-vs-code status conflict: OQ-009 |
| TC-10 | Extra/unknown body fields are silently ignored (e.g. `assignee_id` cannot be set via API) | FIXED | cited+traced | `ticketd/app/server.py:42-52` reads only title/priority; trace `tickets-create-010` |
| TC-11 | Slug edge cases (audit coverage-hunt AD-002): `strip("-")` runs BEFORE `[:64]`, so a truncated slug can end in `-`; a title of only non-ASCII/symbol chars slugs to the empty string `""` (e.g. "Ünïcödé!" — regex keeps only ASCII a-z0-9) | FIXED as-is until OQ-001 rules (the slug ruling should settle these too) | cited | `ticketd/app/util.py:6` (operation order) |
| TC-12 | Priority coercion boundary (audit AD-003): only exact `str()` results "1"/"2"/"3" map — JSON floats (`2.0` → "2.0") and `null` (→ "None") fall into TC-5's 500 path | ASK (same OQ-007) | cited | `ticketd/app/server.py:47-49` |
