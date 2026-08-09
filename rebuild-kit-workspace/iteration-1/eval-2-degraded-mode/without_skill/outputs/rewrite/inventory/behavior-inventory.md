# Legacy behavior inventory

Source of truth: `../../ticketd` as handed over. All line references are to
`ticketd/app/server.py` unless stated. Evidence tags per `../README.md`.

Cross-cutting facts first, then endpoint by endpoint. **Quirks are numbered Q1..Q12**
and referenced from the ADRs, the compat flags in the scaffold, and the parity tests.

## Cross-cutting

- `[S]` No authentication or authorization on ANY endpoint, including
  `/internal/export/csv`. Presumably network-gated `[A]` — nothing in the source
  enforces anything. **Q1**
- `[S]` Storage is a single SQLite file (`db/ticketd.sqlite3`, server.py:14).
  Single-writer semantics may be masking races the code doesn't guard against
  (e.g. reset-token rate limit check-then-insert, lines 85–92, is not atomic). `[A]`
- `[S]` All timestamps are naive local time (`datetime.now().isoformat()`,
  lines 52, 71; `time.time()` epoch floats for reset tokens). Server timezone
  unknown `[U]` — matters for migration (see migration plan).
- `[S]` Legacy schema (`ticketd/db/schema.sql`) defines `users` and
  `tickets.assignee_id`, but **no code path in this codebase ever reads or writes
  `users` or sets `assignee_id`**. Either dead schema, or another system writes the
  SQLite file directly `[U]`. Flagged prominently in `dead-code-and-unknowns.md`. **Q2**
- `[S]` `assignee_id` still appears in API output because handlers return `SELECT *`
  rows verbatim. The rewrite must keep emitting it (null or value) for wire compat.
- `[S]` Errors are ad-hoc JSON bodies (`{"error": "..."}`), never a standard shape.
  FastAPI's default 422 validation shape is DIFFERENT — the scaffold suppresses it on
  compat routes to preserve legacy bodies. **Q3**

## GET /api/tickets  (server.py:27–37)

- `[S]` Optional `?status=` filter, exact string match against the status column.
  Any other query params ignored.
- `[S]` **No pagination — the UI depends on receiving everything** (comment at
  line 35 says client-side filtering relies on it). Preserve; revisit only with row
  counts from prod DB. **Q4**
- `[S]` Ordered `created_at DESC`. Note: ordering is string comparison over ISO text
  in SQLite; equivalent for ISO-formatted values.
- `[S]` Response: JSON array of full row objects (all 8 columns).

## POST /api/tickets  (server.py:40–55)

- `[S]` Body parsed with `get_json(silent=True) or {}` — malformed/absent JSON is
  treated as `{}`, not an error. **Q5**
- `[S]` Empty/whitespace/missing title → `422 {"error": "title_required"}` (Q3 shape).
- `[S]` `priority`: accepted as int or string; `"1"/"2"/"3"` (or ints 1/2/3, via
  `str()`) map to `low/med/high`; default `"med"`. Comment at line 46: both client
  styles must keep working. **Q6**
- `[S]` Any other priority value (e.g. `"urgent"`) passes the handler but violates the
  CHECK constraint → sqlite IntegrityError → HTTP 500. So "invalid priority = 500" is
  the de facto contract. Preserved as-is (a 500, not a 4xx) pending evidence that no
  client depends on... nothing depends on a 500; safe to keep as 500 either way.
- `[S]` Slug from `slugify(title)` (`ticketd/app/util.py`): lowercase, non-alnum runs →
  `-`, trimmed, truncated to 64. **Collisions allowed** — no unique constraint, "Fix DB"
  and "fix db!" share a slug (comment in util.py). Preserve; slugs are apparently
  cosmetic `[A]`. **Q7**
- `[S]` `created_at` = naive local ISO string.
- `[S]` Response `201 {"id": <rowid>, "slug": "<slug>"}` — slug is computed twice
  (line 52 and 55); harmless, same input.
- `[S]` No length limit on title; no strip beyond validation (`title.strip()` result is
  what's stored — leading/trailing whitespace removed).

## GET /api/tickets/{id}  (server.py:58–64)

- `[S]` **Missing ticket → `200` with body `{}`, NOT 404.** Comment at line 62: the
  legacy UI depends on it. Preserve unconditionally until the UI is confirmed migrated.
  **Q8**
- `[S]` Found → full row object.
- `[S]` Route only matches integer ids (Flask `<int:tid>`); `/api/tickets/abc` is a
  Flask 404 HTML page, not JSON. Parity tests cover this loosely (status only).

## POST /api/tickets/{id}/close  (server.py:67–77)

- `[S]` Conditional update: only rows with `status != 'closed'` change; second close is
  a no-op. Response `{"closed": true|false}` — false for already-closed AND for
  nonexistent ids (both 200). **Q9**
- `[S]` `closed_at` = naive local ISO string.
- `[S]` On a real close, emails `watchers@example.internal` with body
  `closed: <title>`, synchronously, AFTER commit. Consequences:
  - SMTP outage → request blocks up to 30s then 500, **but the ticket is already
    closed** (commit precedes send). Clients that retry on 500 get
    `{"closed": false}` on the retry and no email is ever sent. This
    partial-failure quirk is the strongest argument for the outbox (ADR-001). **Q10**
- `[S]` Hardcoded single recipient `watchers@example.internal`; the `users` table is
  NOT consulted for watchers. `[U]` whether that address is an alias/list.

## POST /api/auth/reset  (server.py:80–95)

- `[S]` Rate limit: max 3 requests per rolling hour **per email** (attacker-supplied
  key), counted from the reset_tokens table itself.
- `[S]` **Undocumented bypass: header `X-Internal-Bypass: 1` skips the rate limit**
  (line 84). Callers unknown `[U]` — this is exactly the kind of thing git
  history/access logs must answer. Scaffold keeps it behind a config flag,
  default OFF (ADR-002). **Q11**
- `[S]` Token = `md5(email + time.time())` hex — predictable from email + coarse
  request time, and stored in plaintext. Replaced (ADR-002); handover only said "MD5",
  the source shows it's worse (guessable input, not just weak hash).
- `[S]` No check that the email belongs to any user — tokens are minted and mailed for
  ANY address. (Also means the rate-limit table grows unboundedly; no cleanup job
  exists.) Preserved semantics: always `{"ok": true}` (no account enumeration), but
  ADR-002 notes the open question of whether to keep minting tokens for unknown emails.
- `[S]` Reset email sent synchronously (line 94); on SMTP failure the token row is
  already committed and the client gets a 500.

## POST /api/auth/reset/confirm  (server.py:98–108)

- `[S]` Look up by exact token; valid window 30 minutes (`RESET_WINDOW_MIN`).
- `[S]` **Deliberate: expired and invalid tokens return the SAME `403
  {"error": "invalid_token"}`** (comment, line 104 — non-disclosure). Preserve. **Q12**
- `[S]` Single use: row deleted on success. Note `DELETE ... WHERE token = ?` deletes
  ALL rows with that token value if duplicates exist (possible: no unique constraint).
- `[S]` Success body: `{"ok": true, "email": "<email>"}` — the email is *returned to
  the caller*. **Nothing in this codebase stores or changes passwords**; whatever
  actually performs the reset is a separate consumer of this response `[U]`. Do not
  drop the `email` field.
- `[S]` Expired tokens are never purged, only overwritten by nothing — table grows
  forever.

## GET /internal/export/csv  (server.py:111–115)

- `[S]` Comment: "written for the 2020 audit; no caller since" — dead-code candidate,
  but "no caller" is a claim we cannot verify without access logs `[U]`.
- `[S]` Emits `id,title,status` with **naive comma-joining — titles containing commas
  or newlines produce corrupt CSV**. If we keep the endpoint, byte-compat means keeping
  the corruption; scaffold keeps it behind a flag, default ON, byte-compatible
  (ADR-003).
- `[S]` No auth (Q1) — anyone who can reach the service can dump all tickets.

## Notifier  (ticketd/app/notify.py)

- `[S]` Plain `smtplib.SMTP("smtp.internal", 25, timeout=30)`, no TLS, no auth, no
  retry. `sendmail` is called with the body only — **no headers at all** (no Subject,
  no From/To headers in the payload; envelope only). Real delivered-mail appearance
  unknown `[U]`; the outbox worker reproduces envelope-only sending by default with a
  TODO to confirm against a captured production email.

## Discovered defects (not in the handover notes)

- **L1 — lock poisoning after failed writes.** Found by running the parity suite
  against a local instance of legacy (2026-08-08, see evidence log). The app never
  closes its per-request sqlite connections (`g.db`, server.py:20-24 — no teardown
  handler). When a write fails (e.g. the CHECK-violating priority in Q6), the failed
  transaction's connection lingers until garbage collection and holds a lock;
  until then, unrelated write requests intermittently 500 with `sqlite3
  OperationalError: database is locked`. Caveat: reproduced under modern
  Flask/Python, not the production runtime `[A]` — but the connection leak itself is
  plainly in the source `[S]`. The rewrite has no analogous failure mode
  (session-per-request with proper teardown, Postgres row locks). The parity suite
  retries around it (`_post_retrying_lock_500`) and runs the poisoning test last.

## Not part of the running service

- `[S]` `ticketd/app/legacy_import.py` — self-described one-off 2019 importer, nothing
  imports it. Not ported. Listed in `dead-code-and-unknowns.md`.
- `[S]` Trailing `# tweak 1..3` / `# note` comments in server.py/util.py — noise,
  likely hand-edit artifacts of the handover; no behavior.
