# Draft: Tickets subsystem (list, create, get, close)

Feeds WO-001 (notification decoupling, cross-cutting) and WO-002 (tickets CRUD). Entity reference:
`docs/domain/tickets.md`. All citations against `ticketd/app/server.py` at pinned ref
`1cc113597ea87990e731f02190fc6999e42e7cd8` unless noted.

## GET /api/tickets — list

- Accepts optional `?status=` query param. **statement**: when present, filters to exact match on
  `tickets.status`; when absent, returns all tickets regardless of status.
  fidelity: FIXED. confidence: cited (`server.py:27-34`).
- **statement**: results ordered by `created_at DESC` always, filter or not.
  fidelity: FIXED. confidence: cited (`server.py:36`).
- **statement**: no pagination exists; every matching row returns in one response, every time.
  fidelity: FIXED — explicit code comment states the UI depends on unpaginated full results
  (`server.py:35`), and PB-006 (no UI changes) forecloses changing this now. confidence: cited.
  Flag: `usage-weights.json` shows this is the highest-traffic route (61.75% of sampled requests)
  — an unpaginated table scan on every call is a real scale risk if ticket volume grows, but
  changing it is a UI-breaking contract change, out of scope. Worth an NFR note for a *future*
  rewrite, not actionable here.
- **statement**: response is a JSON array of ticket objects, each with every DB column
  (`id`, `title`, `slug`, `priority`, `status`, `assignee_id`, `created_at`, `closed_at`) —
  `dict(r)` over a `sqlite3.Row` serializes all columns, nothing is excluded.
  fidelity: FIXED. confidence: cited (`server.py:37`).
- **statement**: no error path — malformed `status` values (not `open`/`closed`) simply match zero
  rows, no validation, no 4xx. fidelity: FIXED (absence of validation is itself the observed
  behavior). confidence: cited (`server.py:29-34`, no validation code exists).
- Perf floor (NFR, from PB-004/P2 evidence): p50 25ms / p95 68ms / p99 95ms in the same-day
  sample (`perf-envelopes.json`) — the rewrite should not regress this, treating the sample as
  illustrative given the evidence-quality caveat in `zero-traffic.md`.

## POST /api/tickets — create

- **statement**: `title` is required; request body's `title` is `.strip()`ped, and an
  empty-after-strip title returns `422 {"error": "title_required"}` — missing key, `null`, empty
  string, and whitespace-only strings all hit this branch identically (`body.get("title", "")`
  defaults missing/`None`... actually `.get("title", "")` on a `None` value from a JSON `null`
  would return `None`, not `""` — **ASK candidate**, see below).
  fidelity: FIXED for the empty/whitespace/missing cases. confidence: cited (`server.py:42-45`).
- **statement (was ASK, now RESOLVED — see OQ-008)**: `{"title": null}` explicitly →
  `body.get("title", "")` only substitutes the default when the *key is absent*; since `title` is
  present but JSON `null`, `.get()` returns `None`, and `None.strip()` raises `AttributeError` —
  Flask turns this into an unhandled-exception `500` (HTML error page), not the `422
  title_required` JSON path. **Confirmed empirically in P7** by booting legacy locally and sending
  this exact request — see trace `tickets-create-null-title-900`
  (`verification/replay/traces/tickets-crud.jsonl`) and `docs/open-questions.md#OQ-008`.
  fidelity: FIXED — preserve this exact behavior (including the HTML, non-JSON error body).
  confidence: **traced** (upgraded from inferred). Side finding: this same request can leave the
  legacy sqlite connection in a locked state for subsequent requests on the same process — see
  PB-004 (now traced to root cause) and trace `tickets-crud-lock-cascade-901`. This is legacy's
  own defect, not something WO-002 needs to reproduce beyond the 500-with-null-title behavior
  itself; the connection-locking side effect is exactly what the target stack's connection
  handling should structurally prevent (see PB-004 disposition).
- **statement**: `priority` accepts int-as-string (`"1"`/`"2"`/`"3"`) mapped to
  `low`/`med`/`high`, or any other string passed through unchanged (including the words
  `low`/`med`/`high` themselves, or an invalid value that would violate the DB CHECK constraint
  and 500). Default when the key is absent: `"med"`. fidelity: FIXED (explicit code comment:
  "clients send both, both must keep working," `server.py:46`). confidence: cited
  (`server.py:47-49`).
- **statement**: on success, inserts with `status='open'` (hardcoded), `created_at` = naive local
  `datetime.now().isoformat()`, and returns `201 {"id": <new id>, "slug": <slugify(title)>}`.
  fidelity: FIXED for status/response shape/status-code. The `created_at` naive-time construction
  is PB-010/OQ-006 (pending ruling, default FIXED). confidence: cited (`server.py:50-55`).
- **statement (PB-003/OQ-001)**: no slug-uniqueness check exists; two titles that normalize to the
  same slug both succeed, both get the same `slug` value, nothing disambiguates them. No fidelity
  tag — this is the open question itself. WO-002 implements everything else in this endpoint and
  gates only the collision-handling branch on OQ-001's ruling.

## GET /api/tickets/<id> — get by id

- **statement**: missing ticket → `200 {}` (empty JSON object), NOT `404`. Explicit code comment
  confirms this is deliberate, UI-dependent behavior (`server.py:62`). fidelity: FIXED — this is
  PB-007, and PB-006 (no UI changes) means it cannot be cleaned up in this rewrite. confidence:
  cited, not traced (no captured response bodies exist in the evidence — T1 inactive — so this is
  a source-citation-only claim reinforced by the code's own comment, not confirmed against a real
  request/response pair).
- **statement**: found ticket → `200` with every DB column, same shape as the list endpoint's
  per-item shape. fidelity: FIXED. confidence: cited (`server.py:64`).
- **statement**: `<int:tid>` route converter means non-integer path segments never reach this
  handler at all — Flask returns its own `404` for e.g. `GET /api/tickets/abc` before any app code
  runs. fidelity: FIXED (framework-level behavior, worth preserving the *outcome* — a non-numeric
  id is rejected — even if the new framework's routing mechanism differs; FREE on mechanism, FIXED
  on outcome). confidence: cited (`server.py:58`, Flask converter semantics).

## POST /api/tickets/<id>/close — close

- **statement**: `UPDATE ... WHERE id = ? AND status != 'closed'` — closing an already-closed
  ticket is a no-op: `rowcount` 0, response `{"closed": false}`, `200`, **no email sent** (the
  `if changed:` guard, `server.py:73`, skips notification entirely on the no-op path). fidelity:
  FIXED. confidence: cited (`server.py:68-77`).
- **statement**: closing a non-existent id (no row matches the `WHERE`) behaves identically to
  closing an already-closed one from the caller's perspective: `{"closed": false}`, `200`, no
  email, no error. fidelity: FIXED (same code path, no id-existence check anywhere).
  confidence: cited (`server.py:69-71`, the `UPDATE` simply matches zero rows).
- **statement**: on a real open→closed transition, a synchronous email is sent to the fixed
  address `watchers@example.internal` with body `f"closed: {row['title']}"`, **after** the DB
  commit (`server.py:72` commit, then `:74-76` re-select and send) but **before** the HTTP
  response is returned. fidelity: **REPAIR in WO-001** — this is PB-001's core mechanism. Target:
  the DB transition (`status='closed'`, `closed_at` set) still happens synchronously and
  atomically as part of the request (this part is not the problem and is FIXED); notification
  dispatch is decoupled to run asynchronously after the response is sent, so provider slowness/
  outages no longer affect request latency or availability. See ED-001.
  confidence: cited (`server.py:73-76`) + traced (perf-envelopes.json shows this endpoint's p50 is
  4-5x the non-mail-sending endpoints even under presumably-healthy same-day conditions).
- **statement**: the recipient address is hardcoded, not per-ticket, not configurable, not derived
  from `assignee_id` (which is never populated — see `docs/domain/users.md`). fidelity: FIXED
  (preserve the fixed-address behavior; there is zero evidence any other addressing scheme was
  ever intended — the `watchers` glossary entry documents this isn't really "watchers" in any
  dynamic sense). confidence: cited (`server.py:76`).
