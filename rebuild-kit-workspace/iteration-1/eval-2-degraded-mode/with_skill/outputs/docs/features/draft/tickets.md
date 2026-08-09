# Draft spec — subsystem: tickets

<!-- P4 draft; P8 cuts this into WOs. Confidence: cited (file:line) | inferred (deduced, no
     direct site) | traced T2 (observed by executing the pinned legacy through the harness).
     Degraded mode: no T1/production evidence exists; 'traced T2' is the ceiling here. -->

## Feature: list tickets — GET /api/tickets

- statement: Returns a JSON array of full ticket rows (all 8 columns, including `assignee_id`,
  `slug`, `closed_at` as null when unset), ordered by `created_at` DESC.
  fidelity: FIXED   confidence: cited   evidence: ticketd/app/server.py:27-37
- statement: Ordering is a **string** sort over naive local-time ISO timestamps — correct only
  while timestamps sort lexicographically. Modern must preserve newest-first ordering; the
  column type changes in migration (timestamptz), so ordering becomes temporal, not lexical.
  fidelity: FIXED (outcome: newest-first)   confidence: cited
  evidence: ticketd/app/server.py:36, ticketd/db/schema.sql:8
- statement: Optional `?status=` filter, exact match, **unvalidated** — `?status=bogus` returns
  `[]` with 200, not an error.
  fidelity: FIXED   confidence: cited (branch) + traced T2 (trace tickets-list-004-filter-bogus)
  evidence: ticketd/app/server.py:29-34
- statement: [audit A-03] An EMPTY `?status=` value is falsy, skips the WHERE entirely, and
  returns the FULL dump (not []) — `if status:` truthiness, not presence check.
  fidelity: FIXED   confidence: cited + traced T2 (trace tickets-list-005-filter-empty,
  ratelimit-refund set)   evidence: ticketd/app/server.py:32
- statement: [audit A-14] `ORDER BY created_at DESC` has no tie-break; same-timestamp rows
  order arbitrarily. Modern picks created_at DESC, id DESC as a deterministic tie-break
  (FREE choice, recorded here; microsecond timestamps make ties vanishingly rare).
  fidelity: FIXED (newest-first) / FREE (tie-break)   confidence: cited
  evidence: ticketd/app/server.py:36
- statement: No pagination; in-code comment says the UI depends on the full dump.
  fidelity: FIXED (do not add pagination without a ruling — no PB sanctions it)
  confidence: cited   evidence: ticketd/app/server.py:35

## Feature: create ticket — POST /api/tickets

- statement: Non-JSON or absent body is treated as `{}` (`silent=True` + `or {}`), falling
  through to the title check → 422. [audit A-04] BUT a valid-JSON NON-OBJECT body (`[1]`,
  `"x"`, `5`) is truthy, survives `or {}`, and crashes on `.get` → 500. Modern: 422
  validation error (same FREE sanction class as ED-004; no replay trace exercises it).
  fidelity: FIXED (non-JSON→{} path) / FREE (non-object crash shape → 422)
  confidence: cited (path) / inferred (crash shape)   evidence: ticketd/app/server.py:42-43
- statement: Missing/empty/whitespace-only `title` → 422 `{"error":"title_required"}`.
  fidelity: FIXED   confidence: cited   evidence: ticketd/app/server.py:43-45
- statement: [audit A-05] The STRIPPED title is what persists: `.strip()` reassigns before
  the INSERT, so "  Onboard new hire  " is stored, listed, exported, and emailed as
  "Onboard new hire", and the slug derives from the stripped value.
  fidelity: FIXED   confidence: cited + traced T2 (trace tickets-list-001: stored title of
  ticket 3 is stripped)   evidence: ticketd/app/server.py:43,50-52
- statement: A non-string `title` (e.g. number) raises `AttributeError` on `.strip()` → 500.
  fidelity: FREE (unhandled-crash shape is accidental; modern returns a 422 validation error —
  rationale: 500-vs-422 on garbage input is not plausibly load-bearing, but note the change in
  integration-notes; if replay shows a client sending numeric titles, escalate to ASK)
  confidence: traced T2 (trace tickets-create-badtitle-001: observed 500)   evidence: ticketd/app/server.py:43
- statement: `priority` accepts `"1"/"2"/"3"` (and integers 1/2/3 — `str()` first) mapping
  to low/med/high; absent → `"med"`; the literals low/med/high pass through. [audit A-12]
  A JSON float `2.0` stringifies to "2.0" — NOT an alias — and 500s in legacy via the CHECK;
  modern must treat non-integer numbers as invalid (422 priority_invalid, ED-004a class),
  never coerce 2.0→"med".
  fidelity: FIXED (the alias set is API surface — "clients send both, both must keep working")
  confidence: cited   evidence: ticketd/app/server.py:47-49
- statement: Any other priority value (e.g. `"urgent"`, `4`, `"medium"`) is passed to the
  INSERT where the DB CHECK rejects it → unhandled IntegrityError → 500.
  fidelity: FREE (modern: 422 with a validation error; same rationale + caveat as non-string
  title)   confidence: traced T2 (trace tickets-create-badpriority-001: observed 500)   evidence: ticketd/app/server.py:47-53, ticketd/db/schema.sql:5
- statement: `slug = slugify(title)`: lowercase, `[^a-z0-9]+` runs → `-`, strip `-`, truncate
  to 64 (ticketd/app/util.py:4-6). Not unique; a title of only symbols (e.g. `"!!!"`) yields
  slug `""` and is accepted.
  fidelity: FIXED (derivation algorithm)   confidence: cited (algorithm) + traced T2 (trace tickets-create-004-symbolslug: slug "" accepted)   evidence: ticketd/app/util.py:4-6, ticketd/app/server.py:52
  note: slug uniqueness/purpose is OQ-003; the derivation itself is unambiguous.
- statement: Row inserted with status `'open'`, `created_at = datetime.now().isoformat()`
  (naive local time — flagged by the code's own comment). Modern writes UTC (timestamptz);
  diff rules normalize timestamps (see verification/replay/diff-rules.yaml).
  fidelity: FIXED (status seed) / FREE (timestamp representation — outcome: creation instant
  recorded; naive-localtime explicitly not ported per modern/CLAUDE.md)
  confidence: cited   evidence: ticketd/app/server.py:50-53
- statement: Success → 201 `{"id": <rowid>, "slug": <slug>}` — only these two keys.
  fidelity: FIXED   confidence: cited   evidence: ticketd/app/server.py:55
- statement: On an unhandled write error, legacy leaks the per-request SQLite connection (no
  teardown/rollback anywhere), leaving a write lock that stalls subsequent writes ~5s each
  until GC — observed during golden capture (harness README, "probe isolation").
  fidelity: FREE (connection/transaction hygiene is mechanism; modern uses pooled
  connections with per-request transaction scope)   confidence: traced T2 (harness
  observation)   evidence: ticketd/app/server.py:20-24 (connect without teardown handler)

## Feature: get ticket — GET /api/tickets/<int:tid>

- statement: Non-integer id → 404 from Flask's `<int:>` converter (no JSON body contract).
  fidelity: FIXED (status only; body is framework-default → FREE)   confidence: cited
  evidence: ticketd/app/server.py:58
- statement: Unknown id → **200 with body `{}`** — NOT 404. In-code comment: "historical
  quirk … the legacy UI depends on it."
  fidelity: FIXED (explicitly load-bearing)   confidence: cited
  evidence: ticketd/app/server.py:61-63
- statement: Known id → 200 with the full row dict.
  fidelity: FIXED   confidence: cited   evidence: ticketd/app/server.py:64

## Feature: close ticket — POST /api/tickets/<int:tid>/close

- statement: UPDATE guarded by `status != 'closed'`: closing an open ticket sets
  status='closed' and `closed_at` (naive local time), returns `{"closed": true}`; closing an
  already-closed or nonexistent id changes nothing and returns `{"closed": false}` with 200
  (no 404 distinction).
  fidelity: FIXED   confidence: cited   evidence: ticketd/app/server.py:67-77
- statement: Exactly one notification per successful transition, to hardcoded
  `watchers@example.internal`, body `closed: <title>`; none on no-op close.
  fidelity: FIXED (outcome: recipient, trigger condition, body content) — the *dispatch
  mechanism* is REPAIR, next line.   confidence: cited   evidence: ticketd/app/server.py:73-76
- statement: The send is synchronous in-request (comment: "SMTP outages take ticket-closing
  down with them"); worst case 30s block (notify.py timeout).
  fidelity: REPAIR — PB-001; target: enqueue/dispatch outside the request path; response no
  longer depends on SMTP. divergence: ED-001   confidence: cited
  evidence: ticketd/app/server.py:75-76, ticketd/app/notify.py:1-7
- statement: Partial-failure today: the close is COMMITTED before the send; an SMTP failure
  yields a 500 whose side effect (ticket closed, no email) already happened. Under ED-001 this
  failure mode disappears: modern returns 200 and the email is queued durably.
  fidelity: REPAIR (same PB-001 / ED-001 — this is the defect's observable failure shape)
  confidence: inferred (failure path deduced; capture under T2 fault injection in P7)
  evidence: ticketd/app/server.py:72-76
