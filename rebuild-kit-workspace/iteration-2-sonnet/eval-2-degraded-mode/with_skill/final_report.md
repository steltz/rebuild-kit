# Executor final report — eval-2 with_skill (Sonnet 5)

Ran rebuild-kit P0-P10 serially (app too small for workflow fan-out) in declared degraded mode: rebuild.json.evidence marks runtime_ingestion/data_census/trace_capture_t1 all inactive; every downstream artifact says so.
- legacy/ pinned read-only, verified (test commit under legacy/ rejected by pre-commit hook).
- docs/problem-brief.md: PB-001 (sync email), PB-002 (MD5 tokens) as the two sanctioned defects.
- Full behavioral specs, OpenAPI contract, DDL, 11 schema-validated fixtures; migration plan with dirty-data policies marked ASK pending DB access; 6 work orders across 3 milestones in backlog.md/ledger.json; field guide with a real annotated flow storyboard.
- Bright spot: legacy booted locally (Flask+SQLite, SMTP stubbed) — captured 28 real traces against actual legacy execution, harness self-consistency baseline 28/28, 13 characterization tests live and green.
- P9 audit: dispatched a separate fresh-context agent restricted to legacy source + problem brief + draft specs only. Found and independently re-verified 5 issues (1 contradicted claim on status-filter behavior, 1 bad citation, 2 uncovered crash paths now OQ-008/OQ-009, 2 open questions never cross-referenced) — all corrected in place.
- Found and fixed a real bug in the bundled scaffold.py: since ticketd/ had no .git of its own, git rev-parse HEAD walked up into an unrelated parent repo and would have pinned legacy_ref to that repo's SHA. Corrected by hand to a content-hash pin, documented in rebuild.json.legacy_pin_note. [Note: this bug has since been fixed upstream in scaffold.py's pin_legacy().]
Limitations: verification/replay/expected-divergences.yaml unsigned (WO-003/WO-004 gated on human ruling); modern/ empty by design (run-modern.sh exits with instructions); migration (WO-006) explicitly blocked pending DB access; 9 open questions remain, 2 with pre-generated ruling briefs.
