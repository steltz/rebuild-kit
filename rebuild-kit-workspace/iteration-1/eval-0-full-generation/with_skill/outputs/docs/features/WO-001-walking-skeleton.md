# WO-001 — Walking skeleton: list tickets end-to-end

id: WO-001            depends_on: []                milestone: M0
risk: 0.45 (systemic-first-slice risk: validates stack + twin-boot plumbing; claims all cited+traced)
usage_weight: 0.6175  pain_weight: 0.05             context_budget: ~300 lines   gate: true

Reading list: this file · `modern/CLAUDE.md` · `docs/contracts/openapi.yaml` (GET /api/tickets)
· `docs/migration/target-schema.sql` · `verification/harness/README.md` (modern contract).

**Scope.** Stand up the FastAPI + Postgres application skeleton in `modern/` and implement
exactly one flow — `GET /api/tickets` — end to end (app entry, DB, serialization), plus the
three harness hooks (`harness-boot.sh`, `harness-dump.sh`, `harness-age-token.sh` may stub
until WO-005). This proves the twin-boot plumbing before forty WOs depend on it.

behaviors:
  - statement: GET /api/tickets returns a JSON array of full ticket rows — id, title, slug,
      priority, status, assignee_id, created_at, closed_at; NULLs as JSON null.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:27-37, trace: replay/traces/t2-core.legacy.jsonl#tickets-list-001]
  - statement: No pagination; the UI fetches everything and filters client-side.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:35, PB-005]
  - statement: Optional ?status= exact-match filter; unknown values yield [], never an error.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:29-34, traces: tickets-list-002..004]
  - statement: Ordered created_at DESC.
    fidelity: FIXED
    evidence: [ticketd/app/server.py:36, trace: tickets-list-001]
  - statement: Persistence is Postgres per docs/migration/target-schema.sql; serialization of
      created_at/closed_at as strings (exact format normalized in L3; production format
      decision pending OQ-005 — pick ISO-8601 and record it as a FREE choice).
    fidelity: FREE — rationale: storage/framework mechanism is the whole point of PB-004.
  - statement: App layout, DI, settings, migrations tooling.
    fidelity: FREE — per modern/CLAUDE.md conventions; record choices in ledger free_choices.

acceptance:
  replay_set: tickets-list-* from t2-core (5 traces; no divergences apply)
  tests: verification/characterization/test_tickets.py::test_list_full_rows_newest_first,
         ::test_list_unknown_status_filter_empty  (CHAR_TARGET=modern)
  also: harness self-wiring — `diff-run.sh t2-core` must run to the diff step (other
        traces may fail; the 5 assigned must pass); `harness-dump.sh` output matches
        dump_sqlite.py's shape.
gate_packet_note: M0 sign-off doubles as the human signature on
  verification/replay/expected-divergences.yaml (currently PENDING-HUMAN-SIGNATURE).
escalation: consult ticketd/app/server.py:27-37 only if spec ambiguity found.
