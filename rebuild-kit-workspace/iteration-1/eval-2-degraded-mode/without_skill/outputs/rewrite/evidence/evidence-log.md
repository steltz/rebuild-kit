# Evidence log (append-only)

Record every piece of evidence about legacy ticketd here as it arrives, newest last.
Each entry: date, source, what it establishes, and which inventory items / ADRs /
compat flags it updates. Never edit old entries; supersede them.

---

## 2026-08-08 — Handover source snapshot

- **Source:** contractor-provided source tree at `../../ticketd` (6 files). No git
  history, no logs, no DB.
- **Establishes:** everything tagged `[S]` in `../inventory/behavior-inventory.md`.
- **Caveat:** a source snapshot proves what the code *does*, not what production
  *depends on*. All usage claims remain `[A]`/`[U]`.

## 2026-08-08 — Handover notes (verbal/written, relayed by owner)

- **Source:** handover notes, exact provenance unknown.
- **Claims:** (1) notification emails send synchronously inside requests and block
  them; (2) password-reset tokens are MD5. "That's genuinely all we know."
- **Status:** both confirmed against source (notify.py:6 + server.py:76,94;
  server.py:90). Source additionally shows the MD5 token input is predictable
  (`email + time.time()`), which the notes did not say.

## 2026-08-08 — Characterization run: parity suite vs local legacy instance

- **Source:** legacy source executed locally (scratch copy, fresh SQLite from
  `db/schema.sql`, modern Flask 3 / Python 3.13 — NOT the production runtime; treat
  runtime-sensitive findings as `[A]`).
- **Establishes:** `tests/test_parity.py` passes 24/24 non-SMTP tests against legacy
  (5 SMTP-dependent tests xfail without a mailcatcher), i.e. the suite's encoding of
  quirks Q3–Q9, Q11, Q12 and the CSV byte format matches real legacy behavior, not
  just our reading of the code.
- **New finding:** defect **L1** (post-failure "database is locked" 500s from leaked
  sqlite connections) — added to `../inventory/behavior-inventory.md`.

## 2026-08-08 — Characterization run: parity suite vs rewrite scaffold

- **Source:** rewrite scaffold run locally. No Postgres available in this
  environment, so the run used SQLite with hand-mirrored CHECK constraints — a
  smoke test of wire behavior, NOT a Postgres validation. Re-run against real
  Postgres (`sql/001_initial.sql`) before trusting it.
- **Establishes:** all 29 parity tests pass (including the 5 that legacy can only
  pass with a mailcatcher — rewrite emails go to the outbox). Outbox rows verified:
  correct recipients and legacy-format bodies (`closed: <title>`,
  `reset token: <token>`); worker records SMTP failures with attempts/last_error
  instead of failing requests.

---

<!-- Template for future entries:

## YYYY-MM-DD — <source: git history / access logs / prod DB / interview / ...>

- **Source:** <what exactly, and how obtained>
- **Establishes / refutes:** <finding>
- **Updates:** <inventory section, ADR number, compat flag, intake-checklist item #>
-->
