# Executor final report — eval-1 with_skill (Sonnet 5)

Ran rebuild-kit in spec-patch mode (existing rebuild.json found -> resume path). Blast radius found by grepping OQ-002/PB-003; patched:
- docs/open-questions.md: OQ-002 ruling recorded (reading B, target behavior, no-migration scope, ruled_by Dana Ruiz 2026-08-08).
- docs/problem-brief.md: PB-003 UNDISPOSITIONED -> REPAIR in WO-002.
- docs/features/WO-002-ticket-crud.md: slug fidelity ASK -> REPAIR with target statement + divergence: ED-002.
- verification/replay/expected-divergences.yaml: ED-002 added (PB-003 -> WO-002).
- ledger.json: WO-002 unblocked (awaiting_ruling -> pending, blocked_by_asks cleared).
- guide/decisions.md, guide/then-vs-now.md: regenerated via bundled render_guide.py (never hand-edited): OQ-002 moved to Rulings, ED-002 in sanctioned-changes table, WO-002 REPAIR count updated.
Verified expected-divergences.yaml parses with the repo's mini-YAML loader; ledger.json/rebuild.json remain valid. Committed as one slice (fd1b213) on top of existing P0/P10 history.
Limitations: docs/contracts/ddl.sql (frozen legacy DDL) deliberately left alone; no P9 re-audit performed (audit/ledger.audit metrics were already null/empty from original generation, evidence subsystems inactive); no replay traces exist yet for tickets-*.jsonl (pre-existing gap, not fixable by this ruling); modern/CLAUDE.md still PENDING (unrelated to OQ-002).
