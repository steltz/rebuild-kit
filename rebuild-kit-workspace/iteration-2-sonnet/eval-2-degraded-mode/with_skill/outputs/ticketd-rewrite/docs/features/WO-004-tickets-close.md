# WO-004 — Tickets: close (PB-001 primary REPAIR site)

id: WO-004            depends_on: [WO-002]              milestone: M1
risk: 0.62 (inferred-claim ratio low; REPAIR resting on the same unsigned expected-divergences
  entry as WO-003's ED-001b sibling [ED-001]; PB severity high; no legacy test coverage; the
  DB-commit-before-email-send ordering bug — ticket closes even if the send later fails — is a
  subtle interaction worth a careful read)
usage_weight: 0.20 (static proxy — 1 route, but it's the one every ticket eventually hits)
pain_weight: 0.35 (PB-001's PRIMARY call site — the docstring in legacy/app/notify.py that
  motivated this whole rewrite lives here)
context_budget: ~350 lines (this WO + docs/features/draft/tickets-close.md +
  modern/CLAUDE.md's PB-001 architecture rule + expected-divergences.yaml's ED-001)
gate: true (PB severity high + unsigned expected-divergences.yaml — same STOP as WO-003)

## STOP before implementing

Same as WO-003: `verification/replay/expected-divergences.yaml`'s ED-001 is UNSIGNED. Get a
human ruling before trusting this WO's L3 result.

## Reading list

`docs/features/draft/tickets-close.md` (full behaviors, cited), `modern/CLAUDE.md` PB-001
architecture rule, `verification/replay/expected-divergences.yaml` (ED-001).

## Behaviors

- statement: idempotent close — `open -> closed` transition only; already-closed or nonexistent
  both produce `{"closed": false}`, `200` either way (no way to distinguish from the response).
  fidelity: FIXED
- statement: **PB-001** (primary site) — notification email must not block the response. ALSO
  fix the ordering bug this uncovered: legacy commits the status change BEFORE sending mail with
  no exception handling, so an SMTP failure today returns a 500 to a client even though the
  ticket WAS closed — the client can't tell. The REPAIR target is: response reflects the
  successful DB commit; email dispatch happens out-of-band and CANNOT fail the HTTP response,
  which structurally fixes the client-visibility problem too (that's a consequence of the fix,
  not a separate REPAIR needing its own PB citation — same root cause, same fix).
  fidelity: REPAIR — divergence: ED-001 (UNSIGNED — see STOP above)
- statement: when (and only when) the transition actually happens, notify
  `watchers@example.internal` with body `"closed: {title}"`. Content/trigger condition unchanged
  by the REPAIR — only the dispatch timing/mechanism changes.
  fidelity: FIXED (content + trigger condition) / REPAIR (dispatch mechanism, see above)

## Escalation

`legacy/app/server.py:67-77`, `legacy/app/notify.py:1-7` only if citations are ambiguous.

## Acceptance

- L1: `/api/tickets/{tid}/close` validated against openapi.yaml.
- L2: `verification/characterization/test_tickets.py::test_close_is_idempotent`,
  `::test_close_nonexistent_ticket` pass.
- L3: `verification/harness/diff-run.sh tickets` — `tickets-014` through `tickets-017` traces
  pass, ED-001 diverging exactly as specified (once signed).
- Gate: STOP for human sign-off on the unsigned ED-001 entry before closing.
