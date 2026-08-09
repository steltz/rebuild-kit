# Draft spec — Tickets: list, create, get

<!-- P4. Confidence: cited (file:line) throughout; none traced (P2/P7-T1 inactive this run).
     P9 AUDIT NOTE (fresh-context adversarial pass, see audit/report.md finding F-1): the
     original "when present" wording below for the status filter was CONTRADICTED and has been
     corrected. This note stays as the audit trail; the statement itself is fixed.
     Cross-reference (P9 finding I-2): every route in this file is unauthenticated -- see
     docs/open-questions.md#OQ-004 (is that intentional for an "internal" tool, or a gap?). -->

## GET /api/tickets

- statement: Returns all tickets as a JSON array, each ticket being every column of its row
  (`SELECT *`, `dict(r)` per row). No pagination — comment confirms it's deliberate
  ("the UI relies on getting everything and filtering client-side").
  fidelity: FIXED
  evidence: [legacy/app/server.py:27-37] confidence: cited
- statement: Filters `WHERE status = ?` only when the `status` query param is TRUTHY
  (`if status:`, `server.py:32`) — NOT merely "present." `?status=` (present, empty string) is
  falsy in Python and the filter is silently skipped, returning ALL tickets unfiltered, same as
  omitting the param entirely. This is a corrected statement — see the P9 audit note above; the
  original draft said "when present," which is contradicted by this exact case. No partial
  match, no validation that a non-empty value is a real status value — an unrecognized-but-
  truthy status simply returns zero rows, no error.
  fidelity: FIXED
  evidence: [legacy/app/server.py:29-34] confidence: cited
- statement: Results are ordered `created_at DESC`.
  fidelity: FIXED
  evidence: [legacy/app/server.py:36] confidence: cited
- statement: Response is a bare JSON array (not wrapped in `{"tickets": [...]}` or similar).
  fidelity: FIXED
  evidence: [legacy/app/server.py:37] confidence: cited

## POST /api/tickets

- statement: `title` is required; server-side stripped of leading/trailing whitespace; empty
  (post-strip) is rejected `422 {"error": "title_required"}`.
  fidelity: FIXED
  evidence: [legacy/app/server.py:42-45] confidence: cited
- statement: `priority` accepts either the literal strings `low`/`med`/`high`, OR the strings
  `"1"`/`"2"`/`"3"` which map to `low`/`med`/`high` respectively. Defaults to `"med"` when absent.
  Any other value is passed through verbatim to the INSERT, which would violate the DB CHECK
  constraint — the resulting error surface is untested/unknown (unhandled `sqlite3.IntegrityError`
  -> Flask default 500 today).
  fidelity: FIXED (accepted-value coercion) / ASK (invalid-priority error contract, now
  `docs/open-questions.md#OQ-008` — the P9 audit caught that this draft referenced an OQ that
  was never actually filed; filed now)
  evidence: [legacy/app/server.py:46-49, db/schema.sql:5] confidence: cited
- statement: (P9 coverage-hunt finding, audit/report.md C-1/C-2) two more crash/edge paths in
  the same handler, neither previously spec'd: (a) a non-string `title` (e.g. JSON `{"title":
  5}` or `{"title": null}`) reaches `.strip()` at `server.py:43` and raises `AttributeError` —
  unhandled, Flask default 500; (b) an EXPLICIT `{"priority": null}` does NOT get the `"med"`
  default (the default only applies when the key is absent, `body.get("priority", "med")`) —
  `str(None)` becomes the literal string `"None"`, which falls through to the same untested
  invalid-priority path as (above). Both are now covered by `docs/open-questions.md#OQ-009`.
  fidelity: ASK — docs/open-questions.md#OQ-009
  evidence: [legacy/app/server.py:43, legacy/app/server.py:47] confidence: cited
- statement: `slug` is derived via `slugify(title)` and stored; not guaranteed unique (see
  `docs/open-questions.md#OQ-005`).
  fidelity: FIXED (mechanism), flagged via OQ-005 (uniqueness policy)
  evidence: [legacy/app/server.py:52, legacy/app/util.py:4-6] confidence: cited
  <!-- P9 audit finding F-2: citation corrected from "50-51" to "52" (line 50 is the db().execute(
       call, 51 is the SQL string; slugify(title) itself is on 52, inside the params tuple). -->
- statement: `status` is always `'open'` on create; `created_at` is
  `datetime.now().isoformat()` — naive local time (see `docs/open-questions.md#OQ-001`).
  fidelity: FIXED, flagged via OQ-001
  evidence: [legacy/app/server.py:51-52] confidence: cited
- statement: Success response is `201 {"id": <int>, "slug": <str>}` — note the response
  recomputes `slugify(title)` a second time rather than reusing the value that was inserted;
  since `slugify` is a pure function of `title` this is equivalent in practice, not a bug.
  fidelity: FIXED
  evidence: [legacy/app/server.py:55] confidence: cited

## GET /api/tickets/<int:tid>

- statement: On a found ticket, returns `200` with the full row as JSON.
  fidelity: FIXED
  evidence: [legacy/app/server.py:64] confidence: cited
- statement: On a missing ticket, returns `200` with an **empty JSON object `{}`**, not `404`.
  Comment explicitly names this "historical quirk ... the legacy UI depends on it."
  fidelity: FIXED — this is the clearest FIXED case in the whole app: evidenced, and the evidence
  itself asserts a caller dependency.
  evidence: [legacy/app/server.py:58-64] confidence: cited
