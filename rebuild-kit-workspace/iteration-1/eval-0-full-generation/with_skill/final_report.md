# Executor final report — eval-0 with_skill

I executed the full rebuild-kit pipeline (P0–P10, serial mode — proportional for a 168-LOC target) and produced a complete rewrite workspace, a git repo with `ticketd/` pinned as a read-only gitlink (chmod + pre-commit guard, both tested).

- Problem brief: 5 PB entries harvested from testimony (sync-SMTP outage, MD5 tokens, slug collisions, FastAPI+Postgres stack, no-UI-changes), all dispositioned; NFR targets derived from the 30-day log's latency envelopes.
- Evidence (P1/P2, script-generated): inventory.json (all 7 routes spot-checked), usage-weights.json (list route = 62% of traffic), perf-envelopes.json (NFR floors), hotspots.md (3 of 4 legacy commits are reset-flow hotfixes), zero-traffic report.
- Specs: overview + domain docs; 7 draft feature specs with 43 cited claims; validated OpenAPI, verbatim DDL, JSON Schema + 7 fixtures (round-trip validated), Hyrum's-law notes (200-{} quirk, no pagination, priority coercion).
- Verification harness: twin-boot scripts, T2 driver, 34 replay traces with legacy goldens captured live at the pin (booted legacy under an SMTP capture sink; self-test 34/34), 21-test characterization suite passing 21/21 against the legacy boot. diff-rules.yaml justified per rule; 3-entry expected-divergence manifest (ED-001/002/003).
- Migration: 25 census probes generated (awaiting prod access), mapping with ASK-gated policies, target Postgres schema, reconciliation queries, cutover/rollback doc.
- Backlog: 8 work orders across 4 gated milestones (M0 walking skeleton → M1 tickets/outage fix → M2 auth reset → M3 migration), risk-scored, ledger records the harness baseline.
- Adversarial audit (serial approximation, labeled): 43 claims — 41 confirmed, 1 contradicted (fixed), 1 unverifiable (annotated); 4 new coverage items; 100% branch and problem coverage; metrics in ledger.
- Field guide: orientation, legacy/modern chapters, 2 flow storyboards from real captured traces, then-vs-now, decisions.
- 9 OQ entries with 7 ruling briefs (slug fix OQ-001, bypass header OQ-002, CSV-export drop OQ-003, mail mechanism OQ-004, timezone policy OQ-005 blocking migration WO, reset-confirm consumer OQ-006, invalid-priority 500 OQ-007) plus two evidence conflicts found in the provided log.

Limitations: no prod DB access → census generated not run (degraded mode recorded; migration WO elevated risk); no payload capture → replay is T2 scripted, not T1; audit independence serial-approximated; harness boots legacy on Flask 3.1 vs prod "Flask 1.x era" (noted); expected-divergences.yaml needs human signature at/before M0 gate.
