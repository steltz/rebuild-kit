# Problem Brief — ticketd

<!-- Captured 2026-08-08 from the rewrite requester (non-interactive intake — see
     "Open intake questions" below). Human testimony: third evidence class alongside code +
     traces. Every entry must end the pipeline dispositioned; P9 blocks assembly otherwise. -->

## Motivation

ticketd is an internal ticket tracker inherited from a contractor with no git history, no
access logs, and (for now) no production database access. The requester does not want to wait
for that evidence to arrive before starting: this workspace is generated code-only, in
rebuild-kit's degraded mode, on the explicit instruction to "layer the evidence in later." Target
stack is FastAPI + PostgreSQL (human decision, stated directly in the rewrite request — see
`rebuild.json.target_stack`). Beyond the two defects below, no further motivation, no scale/SLO
targets, and no team-shape context were supplied — see Open intake questions.

## Register

### PB-001 — Notification emails send synchronously inside requests and block them
- kind: defect
- severity: high
- reported_by: handover notes (via rewrite requester)   affected_area: notifications / ticket
  close / auth reset
- detail: `app/notify.py:send_mail` opens a blocking `smtplib.SMTP` connection
  (`timeout=30`) and calls `sendmail` synchronously. Both call sites —
  `app/server.py:76` (`close_ticket`) and `app/server.py:94` (`request_reset`) — invoke it
  in-request, so the HTTP response does not return until SMTP completes. The module docstring
  itself records the cost: "~2s typical, 30s on provider trouble" (`app/notify.py:1`).
- reproduction: no trace available (no runtime evidence granted this run); reproducible by code
  inspection — any SMTP slowdown or outage stalls `POST /api/tickets/<id>/close` and
  `POST /api/auth/reset` for up to the 30s socket timeout, and a hard SMTP failure (e.g.
  connection refused) raises inside the request handler with no try/except, so the request
  fails after paying the connection-timeout cost.
- disposition: REPAIR in WO-004 (target: ticket-close and reset-request responses must not block
  on SMTP — enqueue email dispatch instead of sending in-request. The dispatch *mechanism*
  itself — FastAPI `BackgroundTasks` vs. a table-backed outbox vs. an external queue — is FREE;
  only the "don't block the response" outcome is REPAIR-mandated. See `modern/CLAUDE.md`
  architecture rules and WO-004.)

### PB-002 — Password-reset tokens are generated with MD5
- kind: defect
- severity: high
- reported_by: handover notes (via rewrite requester)   affected_area: auth / password reset
- detail: `app/server.py:90` — `token = hashlib.md5(f"{email}{time.time()}".encode()).hexdigest()`.
  MD5 is not a cryptographically secure token-generation mechanism (fast to brute-force, and the
  input entropy is just an email address plus a wall-clock timestamp — no CSPRNG involved).
  Tokens are stored and matched by exact string equality (`app/server.py:101-102`), with no
  additional secret-generation step.
- reproduction: no trace available; reproducible by code inspection — token predictability
  depends only on guessing/observing the request time window and the target email, both of which
  are low-entropy.
- disposition: REPAIR in WO-003 (target: generate reset tokens with a CSPRNG of adequate length,
  e.g. `secrets.token_urlsafe`, keeping the existing outcome contract: single-use, expires after
  `RESET_WINDOW_MIN`, same error body for expired/invalid per PB-defect-adjacent non-disclosure
  behavior which is FIXED, not a defect — see WO-003 notes)

## NFR targets

None supplied this run. No SLOs, scale targets, or operability goals were given in the rewrite
request or handover notes. Recorded as an open intake question below rather than invented.

## Non-goals

None supplied this run. In particular it is not known whether: multi-tenant support, ticket
assignment workflow changes, or the `/internal/export/csv` endpoint's fate are in scope. Recorded
as open intake questions.

## Open intake questions

- **Scale / SLOs / team shape** — not supplied. Blocks setting real NFR targets and perf-envelope
  floors (P2 is inactive anyway, so there is nothing to floor against yet).
- **Non-goals** — not supplied. Nothing has been explicitly excluded from the rewrite.
- **Runtime evidence timeline** — "no production database access yet (maybe in a few weeks)."
  This workspace should be revisited via spec-patch once logs/APM/DB access exist; several specs
  below are capped at lower confidence pending that evidence (see `rebuild.json.evidence`).
- **Everything not named in the handover notes** — the requester was explicit that PB-001 and
  PB-002 are "genuinely all we know." Several other suspicious behaviors were found by reading
  the code during P3/P4 (undocumented rate-limit bypass header, get-ticket-by-id returning `200`
  with `{}` instead of `404`, slug collisions, an apparently dead CSV export endpoint, an unused
  importer module). None of these were reported by a human, so none are promoted to PB entries
  here — per the brief's role as the FREE/REPAIR whitelist, an un-reported behavior stays FIXED
  (ported as-is) unless a human rules on it. They are logged as PB-proposal entries in
  `docs/open-questions.md` instead, for a human to disposition.
