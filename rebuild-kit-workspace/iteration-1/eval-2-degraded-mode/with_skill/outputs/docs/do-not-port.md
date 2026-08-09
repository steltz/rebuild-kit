# Do Not Port — negative space, with evidence

<!-- Binding on the executor. Each entry: what, why, evidence. Additions require evidence;
     removals require a ruling. -->

## DNP-001 — app/legacy_import.py (one-off 2019 spreadsheet importer)
- what: entire module.
- why: dead code — zero inbound imports (inventory.json dependency_edges), zero route
  references, and its own docstring says "One-off importer from the 2019 spreadsheet era.
  Nothing imports this module." (ticketd/app/legacy_import.py:1). Static evidence is
  conclusive here (module-level, not route-level — needs no traffic data).
- confidence: high (code-only, but corroborated twice over).

## DNP-002 — /internal/export/csv (CONDITIONAL — held by OQ-001)
- what: the CSV export route.
- why: in-code comment "written for the 2020 audit; no caller since"
  (ticketd/app/server.py:112). Cannot be confirmed dead without logs (none exist), so this
  entry is INACTIVE until OQ-001 is ruled. Until then WO-007 exists and is blocked.
- confidence: pending ruling.

## DNP-003 — Headerless raw-body SMTP messages
- what: passing the bare body string as SMTP DATA with no Subject/From/To headers
  (ticketd/app/notify.py:7), and the hardcoded host `smtp.internal` (ticketd/app/notify.py:6).
- why: transport mechanism, not behavior — the required outcomes (recipient + content) are
  specified in the notifications spec; modern sends well-formed MIME via env-configured
  transport (modern/CLAUDE.md). Sanction: mechanism-FREE per P4 notifications spec; PB-001
  already forces this code path to be rebuilt.

## DNP-004 — Naive local-time timestamp writes
- what: `datetime.now().isoformat()` written to created_at/closed_at
  (ticketd/app/server.py:52,71 — the code's own comment flags it: "naive local time!").
- why: representation, not behavior; modern writes UTC timestamptz. Ordering outcome
  (newest-first list) is preserved and replay-checked; migration converts stored values
  (docs/migration/mapping.md owns the timezone assumption — see census).

## DNP-005 — Unused import and scratch comments in server.py
- what: `import smtplib` in server.py (unused — send_mail is imported from app.notify;
  ticketd/app/server.py:4) and trailing scratch comments `# tweak 1/2/3`
  (ticketd/app/server.py:120-122), `# note` (ticketd/app/util.py:7).
- why: inert cruft; nothing references them.
