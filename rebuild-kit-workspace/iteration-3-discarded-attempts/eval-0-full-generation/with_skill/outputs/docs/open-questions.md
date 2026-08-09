# Open Questions — ASK register & PB proposals

<!-- Executor + generator both append here. Never delete entries; rulings are appended.
     Each new OQ gets a ruling brief generated into guide/briefs/ (templates/ruling-brief.md). -->

## OQ-001 — What collision-resolution scheme should ticket slugs use?
- raised_by: generator P0 (from PB-003 testimony)
- kind: ambiguity
- readings:
  - A: numeric suffix on collision (`fix-db`, `fix-db-2`, `fix-db-3`, ...) — simple, human-legible,
    but suffix-order depends on insertion order and isn't stable if an earlier ticket is retitled.
  - B: append a short id/hash disambiguator only when needed (`fix-db`, `fix-db-a1b2`) — stable
    regardless of insertion order, less legible.
  - C: always suffix with the ticket's own numeric id (`fix-db-1042`) — trivially unique, fully
    stable, but changes the "clean slug" case that currently exists (single tickets get a suffix
    they didn't need before) — a visible behavior change PB-003 doesn't obviously sanction.
  - No evidence in `legacy/` favors any reading — the legacy code has no collision handling at
    all (`legacy/app/util.py:4-6`, no `UNIQUE` constraint at `legacy/db/schema.sql:4`).
- blocks: [WO-001] (finalizing exact suffix scheme + `docs/migration/mapping.md` backfill policy
  for already-colliding slugs in existing data). Does NOT block M0 — M0 may ship reading B
  (id-suffix-on-collision) as a placeholder FREE choice, explicitly flagged for revisit.
- ruling: PENDING

## OQ-002 — Does `/internal/export/csv` need to exist in the rewrite?
- raised_by: generator P1 (coverage hunt)
- kind: discrepancy
- readings:
  - A: dead — comment says "written for the 2020 audit; no caller since" (`legacy/app/server.py:112`),
    zero requests to `/internal/export/csv` in the one-hour access-log window (see P2 evidence
    notes — window is short, so absence there is weak evidence on its own), zero inbound
    references from any other module.
  - B: still relied on out-of-band (e.g. a human running curl once a quarter for an audit that
    doesn't show up in a one-hour log sample) — the comment only claims no *programmatic* caller.
- blocks: [] (flags gate review only; a `do-not-port.md` candidate either way, see that file)
- ruling: PENDING

## OQ-003 — Should `legacy_import.py` (2019 spreadsheet importer) be ported?
- raised_by: generator P1 (coverage hunt)
- kind: discrepancy
- readings:
  - A: dead — "Nothing imports this module" (`legacy/app/legacy_import.py:1`), zero inbound
    references anywhere in the tree, no route wires it up.
  - B: kept around as a documented one-off migration script, not meant to be imported by the
    app itself — its absence from the import graph is by design, not evidence of abandonment.
- blocks: [] (flags gate review only)
- ruling: PENDING

## OQ-101 — No captured trace/incident timeline for the June SMTP outage
- raised_by: generator P0 (intake gap, non-interactive run)
- kind: inferred-only
- readings:
  - Only source: the commissioning narrative ("closing tickets was down for 40 minutes"). No
    log lines, APM export, or ticket/incident-tracker reference was supplied this run.
- blocks: [] (does not block WO-002; the code-level mechanism — synchronous `send_mail()` in
  the request path — is independently evidenced at `legacy/app/server.py:76,94` and
  `legacy/app/notify.py:6`, so the REPAIR target doesn't depend on the incident trace. Flags
  gate review for WO-002 only insofar as severity/priority weighting is concerned.)
- ruling: PENDING

## OQ-102 — `ops/access.log` does not match its "~30-day" description
- raised_by: generator P2 (runtime evidence ingestion)
- kind: discrepancy
- readings:
  - A: the log provided (`legacy/ops/access.log`, 2000 lines) spans exactly
    2026-07-12T10:00:00Z–10:59:59Z (one hour), one IP pool, one user
    (`jdoe@corp.example.com`), one user-agent (`svc-ui/2.1`) — this reads as a synthetic
    fixture generated for this exercise, not a production capture.
  - B: a real ~30-day log exists somewhere else and wasn't the file handed to this run.
- blocks: [] (usage-weights.json / perf-envelopes.json are still generated from what exists,
  but every artifact deriving from them is marked with this caveat; do not treat P8's
  usage-weight-driven ordering as validated against real traffic until this is resolved)
- ruling: PENDING

## OQ-103 — Does the rewrite need real request authentication/authorization?
- raised_by: generator P0 (intake gap)
- kind: inferred-only
- readings:
  - A: no auth needed — legacy has none (`legacy/app/server.py` has no auth/session middleware
    on `/api/tickets*`; only the reset-password *flow* touches identity), so the API is assumed
    to sit behind a perimeter control (internal network, gateway) not visible in this codebase,
    and the rewrite should keep the same posture.
  - B: auth should be added now — the rewrite is a natural point to close this gap, especially
    since PB-002 already flags the reset-token security posture.
- blocks: [] (no WO currently assumes B; adding real authN/authZ absent a ruling would be an
  unsanctioned feature per design principle 9 — "sanctioned change only")
- ruling: PENDING

## OQ-104 — Data retention policy for reset tokens / closed tickets in Postgres
- raised_by: generator P0 (intake gap)
- kind: inferred-only
- readings:
  - No testimony either way. Legacy never expires/purges `reset_tokens` rows (confirm-reset
    deletes on successful use only, `legacy/app/server.py:106`; there is no cleanup job in the
    tree) and never archives/deletes old closed tickets.
- blocks: [] (P6 migration plan proceeds with "carry everything over, no retention policy
  assumed" as the default, flagged for a ruling before it's treated as final)
- ruling: PENDING
