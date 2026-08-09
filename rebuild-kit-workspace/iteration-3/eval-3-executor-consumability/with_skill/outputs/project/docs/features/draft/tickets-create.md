# Draft spec: POST /api/tickets (create)

usage_weight: 0.2115 (second-highest-traffic route)

## Happy path
- `POST /api/tickets`, JSON body `{title, priority?}`.
- `title` trimmed; empty/whitespace-only → 422. `priority` normalized; defaults `"med"`.
- `slug = slugify(title)`; `status` hardcoded `'open'`; `created_at = datetime.now().isoformat()`.
- Insert, `201` with `{id, slug}`.

## Behaviors

- statement: Missing or empty/whitespace-only `title` returns `422 {"error": "title_required"}`.
  fidelity: FIXED
  evidence: [legacy/app/server.py:43-45]
  confidence: cited

- statement: `priority` is accepted as either the strings `"1"/"2"/"3"` (mapped to
    `low`/`med`/`high`) or already as `low`/`med`/`high` directly; any other string is passed
    through as-is to the INSERT, where the DB `CHECK` constraint rejects it and the request
    fails with an uncaught `sqlite3.IntegrityError` (500, not a handled 4xx).
  fidelity: FIXED (the coercion) / the 500-on-invalid-priority path is a genuine gap
  evidence: [legacy/app/server.py:47-49, legacy/db/schema.sql:5]
  confidence: cited
  note: the comment "clients send both, both must keep working" (server.py:46) makes the
    coercion itself explicitly load-bearing/intentional — FIXED, not incidental. The
    uncaught-500-on-garbage-priority path has no comment either way; not brief-mentioned, so
    left FIXED (reproduce the 500) rather than silently hardened into a 422 — silently
    "improving" error handling nobody flagged would be unsanctioned scope creep. If a human
    wants this cleaned up, it needs a PB entry first (file as PB proposal if the executor
    disagrees at implementation time).

- statement: If `priority` is omitted from the request body entirely, defaults to `"med"`.
  fidelity: FIXED
  evidence: [legacy/app/server.py:47]
  confidence: cited

- statement: `slug` is computed once from `title` via `slugify()` and stored; not guaranteed
    unique (PB-003).
  fidelity: REPAIR in WO-005 — outcome: unique. Mechanism: ASK, OQ-001.
  evidence: [legacy/app/server.py:51-52 (INSERT + slugify(title) in the parameter tuple —
    CORRECTED after P9 audit: line 51 alone is only the SQL string, it does not itself contain
    the slugify() call; the call is on line 52), :55 (recomputed for the response);
    legacy/app/util.py:4-6]
  confidence: cited
  divergence: (pending — ED entry to be added once OQ-001 rules the mechanism)

- statement: New tickets are always created with `status='open'`; there is no way to create a
    ticket in any other status via this route.
  fidelity: FIXED
  evidence: [legacy/app/server.py:51]
  confidence: cited

- statement: `created_at` is `datetime.now().isoformat()` — naive local time (see OQ-003).
  fidelity: ASK (PB proposal OQ-003) — until ruled, modern default is UTC per modern/CLAUDE.md,
    without blocking this WO.
  evidence: [legacy/app/server.py:52]
  confidence: cited

- statement: Response is `201 {"id": <new id>, "slug": <computed slug>}`. Note the slug is
    recomputed a second time for the response (`slugify(title)` called again at line 55 rather
    than reusing the value inserted) — same input, same deterministic function, so no
    observable difference today, but worth flagging: if slug generation ever becomes
    non-deterministic (e.g. as part of WO-005's collision fix), these two call sites diverging
    becomes a real bug class. WO-005 must compute the slug exactly once and reuse it.
  fidelity: FIXED (the response shape and status code) / the double-computation is an
    implementation detail, FREE, but the *single-computation* requirement becomes a hard
    constraint once WO-005 makes slugification stateful (must check the DB for collisions)
  evidence: [legacy/app/server.py:50-55]
  confidence: cited

- statement: **Added after P9 audit — previously uncovered branch.** `title: null` (key
    present, value `null`) is NOT the same code path as a missing/empty title. `body.get(
    "title", "").strip()` only returns the `""` default when the key is *absent*; when present
    with value `null`, `.get()` returns `None`, and `None.strip()` raises `AttributeError` →
    uncaught 500. Same failure class for any non-string JSON `title` (number, bool, list,
    dict). This is distinct from the documented, gracefully-handled "missing/empty/
    whitespace-only" case (first behavior in this file, 422).
  fidelity: FIXED (as-coded gap; not brief-mentioned)
  evidence: [legacy/app/server.py:43]
  confidence: traced (P9 audit finding)

- statement: **Added after P9 audit — previously uncovered branch.** A title composed entirely
    of characters `slugify()` strips (e.g. `"!!!"`, `"###"`, `"   ---   "` after the
    non-whitespace check passes) produces `slug = ""`. This satisfies `title`'s non-empty
    check (the title itself isn't blank) and satisfies `slug TEXT NOT NULL` (NOT NULL rejects
    only NULL, not empty string) — so the ticket is created successfully with an empty slug.
    Every such title collides on the same `""` slug, which is arguably a MORE severe instance
    of PB-003 than the brief's own "Fix DB"/"fix db!" example, since it silently affects an
    entire class of titles rather than two similarly-named ones.
  fidelity: FIXED (current behavior) — but explicitly in-scope for WO-005 (PB-003) as the
    same uniqueness fix should address this case too, not just literal-collision titles;
    the OQ-001 mechanism ruling should be read with this case in mind.
  evidence: [legacy/app/server.py:51-52, legacy/app/util.py:4-6 (regex collapse + strip("-")),
    legacy/db/schema.sql:4 (`slug TEXT NOT NULL` — NOT NULL only, no length/non-empty check)]
  confidence: traced (P9 audit finding)

- statement: **Added after P9 audit — previously uncovered branch.** A JSON body that parses
    successfully but is not a dict (bare list/string/number/bool — anything JSON-truthy) is not
    caught by `request.get_json(silent=True) or {}` (the `or {}` fallback triggers only on
    JSON-falsy bodies). `body.get("title", "")` on a non-dict raises `AttributeError` →
    uncaught 500. Same pattern as `request_reset`/`confirm_reset` — see
    docs/features/draft/auth-reset-request.md.
  fidelity: FIXED (as-coded gap; not brief-mentioned)
  evidence: [legacy/app/server.py:42-43]
  confidence: traced (P9 audit finding)

## Error paths
- `title` empty → `422 {"error": "title_required"}` (only explicit error handling in this route).
- Invalid `priority` string → uncaught DB `CHECK` violation → 500 (see above, FIXED-as-is).
- `title: null` or non-string `title` → uncaught `AttributeError` → 500 (P9 finding, see above).
- Non-dict JSON body → uncaught `AttributeError` → 500 (P9 finding, see above).
- Back-to-back requests where one hits an uncaught exception mid-transaction can cascade into
  `sqlite3.OperationalError: database is locked` on the NEXT write request — see
  `docs/open-questions.md` OQ-010 (found by actually executing the app under the replay
  harness, not by reading). This is why `verification/replay/inputs/tickets-create.jsonl`
  deliberately orders its intentional-500 case last.

## Acceptance
  replay_set: tickets-create-*.jsonl (happy path, missing title, empty title, whitespace-only
    title, numeric priority, word priority, omitted priority, invalid priority [expect 500])
    — captured T2 golden covers all of the ABOVE. **Not yet extended** to cover the three
    P9-audit findings (title:null, empty-slug, non-dict body) — add before WO-001/WO-005 close.
  tests: characterization/tickets/create.spec
