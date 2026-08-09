## Summary

I picked up WO-001 ("walking skeleton") — the highest-priority unblocked work order per `ledger.json`/`backlog.md` — and implemented it end to end.

**Built:**
- `modern/`: a FastAPI + Postgres app (SQLAlchemy 2.x/psycopg3, Alembic migrations, Pydantic schemas) implementing `GET /api/tickets` and `POST /api/tickets`, reproducing legacy behavior exactly — including its as-coded gaps (uncaught 500 on invalid `priority`, on non-dict JSON bodies, on null/non-string `title`) via a global exception handler that matches Werkzeug's default 500 page byte-for-byte.
- `verification/harness/run-modern.sh`: replaced the generated stub with a real implementation that provisions a disposable Postgres cluster per replay suite.
- `verification/harness/drive_inputs.py`: extended to dump Postgres state (was sqlite-only), and fixed a real latent bug — a case-sensitive `Content-Type` header lookup that silently broke JSON parsing against any server emitting lowercase headers (uvicorn does; Werkzeug's dev server happened not to). Found only by actually running the harness against modern/, not by reading.
- `stop.sh`: extended (backward-compatibly) to also tear down the per-suite Postgres cluster.
- Unit tests for the slug logic, plus the FREE-choice record in `ledger.json`.

**Verified:** L1 (contract fixtures) pass 6/6; L3 — the acceptance oracle — passes 12/12 traces across both `tickets-list` and `tickets-create`, including full DB-state parity. L2 passes for all in-scope cases when suites run in isolation; running the entire (mostly-unimplemented) golden set together shows expected cross-suite state contamination from an out-of-scope suite's own fixture calling the now-live create route — documented, not a defect.

**Limitations / open items**, all recorded in `guide/briefs/M0-gate-packet.md`:
- WO-001 is a **gate** work order — per the executor loop I did not mark it "done." `ledger.json` records it `awaiting_gate_approval`; the gate packet requests human sign-off before Milestone 1 starts.
- `pre_sql` fixture seeding against Postgres isn't implemented in `drive_inputs.py` (not needed by WO-001; flagged for whichever WO needs it next, likely WO-003/008).
- Postgres sequences are non-transactional (unlike SQLite rowids), a real behavioral difference noted for future suite authors, though it doesn't affect any current acceptance criteria.
- OQ-001 and OQ-002 remain unruled, as expected — WO-001 doesn't depend on either.

Work is committed locally on `main` (no remote configured, nothing pushed).