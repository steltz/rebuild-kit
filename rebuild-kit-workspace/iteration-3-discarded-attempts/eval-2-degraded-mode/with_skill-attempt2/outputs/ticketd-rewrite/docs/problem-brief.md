# Problem Brief — ticketd

<!-- Captured 2026-08-09 from the handover conversation (Nicholas Stelter, product owner, no
     contractor available). No git history, no access logs, no production DB access at intake
     time. Human testimony: third evidence class alongside code + traces. Every entry must end
     the pipeline dispositioned; P9 blocks assembly otherwise. -->

## Motivation

ticketd (internal ticket tracker) was handed over by a contractor with no git history and no
access logs. The team wants to replatform it to FastAPI + Postgres rather than continue
maintaining the inherited Flask/sqlite codebase, and does not want to wait for production
database access (expected "in a few weeks") to start the rewrite. This brief is intentionally
thin: intake happened without the contractor present, so it captures only what the handover
notes stated plus what the requester could confirm live. Everything else observed during code
reading is routed to `docs/open-questions.md` as generator-raised PB proposals, never asserted
here as testimony — see Design Principle 1/9 (evidence-or-ASK, sanctioned change only).

## Register

### PB-001 — Notification emails block the request thread
- kind: defect
- severity: high
- reported_by: handover notes (contractor, via requester) — no named individual
- affected_area: `app/notify.py`, `app/server.py:close_ticket`, `app/server.py:request_reset`
- detail: `send_mail` opens a synchronous SMTP connection (`smtplib.SMTP`, 30s timeout) inside
  the request handler for both ticket-close notifications and password-reset emails. Confirmed
  in code: `legacy/app/notify.py:6` (docstring: "Blocks the request thread; ~2s typical, 30s on
  provider trouble."), called synchronously at `legacy/app/server.py:76` and
  `legacy/app/server.py:94`. An SMTP outage or slowdown stalls ticket-closing and password-reset
  requests for up to 30s per request.
- reproduction: no trace available (no access logs / APM). Reproduction is by source inspection
  only — see citations above. Static/derived (T3) evidence only; see `rebuild.json.evidence`.
- disposition: REPAIR in WO-002 (see `docs/features/WO-002-async-notifications.md`)

### PB-002 — Password-reset tokens use MD5
- kind: defect
- severity: high
- reported_by: handover notes (contractor, via requester) — no named individual
- affected_area: `app/server.py:request_reset`
- detail: reset tokens are generated as `hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()`
  (`legacy/app/server.py:90`) — a fast, non-cryptographic hash of low-entropy, guessable input
  (email + wall-clock time), stored in a single unindexed table (`reset_tokens`, no primary key —
  `legacy/db/schema.sql:18-22`). Tokens are single-use (deleted on confirm,
  `legacy/app/server.py:106`) and expire after 30 minutes (`RESET_WINDOW_MIN`,
  `legacy/app/server.py:16,103`), which somewhat bounds the exposure, but the generation
  mechanism itself is weak and collision/predictability risk is real.
- reproduction: no trace available. Source inspection only (T3).
- disposition: REPAIR in WO-001 (see `docs/features/WO-001-reset-token-mechanism.md`)

## NFR targets

None supplied at intake. See "Open intake questions" — no SLOs, scale targets, or team-shape
constraints were given. The rewrite plan assumes modest internal-tool scale (single team,
low-hundreds of tickets, not public-facing) based on the app's own comments (`legacy/db/schema.sql`
has no volume markers; `legacy/app/server.py:35` notes the UI fetches all tickets with no
pagination) — this is an *inference*, not a target, and is logged as OQ-003 for confirmation.

## Non-goals

None supplied at intake. Nothing was ruled explicitly out of scope. See "Open intake questions."

## Open intake questions

Recorded here per P0 rules for non-interactive runs — harvest what was given, log the rest as
gaps rather than inventing testimony. Promoted to the formal `docs/open-questions.md` register
as OQ-001 to OQ-006 (generator-raised, `kind: pb-proposal` or `ambiguity` as applicable) so they
carry IDs, evidence, and block/gate tracking:

- Target scale, SLOs, and operability expectations (e.g. expected ticket volume, concurrent
  users, uptime expectations) — unknown.
- Whether any other consumer (e.g. a legacy frontend not included in this handover) depends on
  quirks like the `200 {}` response for a missing ticket, or the dual int/string `priority`
  encoding — unknown; no frontend source was handed over.
- Whether the undocumented `X-Internal-Bypass` header on `/api/auth/reset` is an intentional
  operational backdoor (e.g. for internal tooling/tests) or leftover debug code — unknown.
- Whether the naive local-time (no timezone) timestamps in `created_at`/`closed_at` are a known
  and accepted limitation or an unrecognized bug — the contractor's own code comment
  (`legacy/app/server.py:52`, "naive local time!") suggests self-awareness but no disposition was
  given.
- Whether `app/legacy_import.py` (2019 spreadsheet importer, confirmed unreferenced anywhere in
  the codebase) should be ported at all, or is purely historical.
- Non-goals and explicitly out-of-scope improvements — unknown; assume "nothing beyond PB-001/
  PB-002 is sanctioned to change" until ruled otherwise (Design Principle 9).

These do not block P0–P8 (degraded-mode generation proceeds), but each blocks the WOs noted in
`docs/open-questions.md` from closing, and several flag gate review at milestone close.
