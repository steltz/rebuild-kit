The workspace is updated and committed. Summary:

**Ruling propagated (OQ-002):** slugs must be unique; on collision append a numeric suffix (`-2`, `-3`, ...); existing stored slugs are not migrated.

**Changes made** (`ticketd-rewrite-root`, commit `31c2afe`), following the skill's spec-patch procedure:
- `docs/open-questions.md` — OQ-002 ruling recorded (append-style, original readings preserved)
- `docs/problem-brief.md` — PB-003 dispositioned `REPAIR in WO-002`
- `docs/features/WO-002-ticket-crud.md` — slug behavior's fidelity flipped `ASK → REPAIR`, target behavior spelled out, linked to `ED-002`
- `verification/replay/expected-divergences.yaml` — new `ED-002` entry (legacy collision → expected unique+suffix)
- `ledger.json` — WO-002 unblocked (`awaiting_ruling → pending`, `blocked_by_asks` cleared)
- `guide/decisions.md`, `guide/then-vs-now.md` — re-rendered via `render_guide.py` (never hand-edited)
- `guide/briefs/OQ-002-ruling-brief.md` — backfilled (this ruling brief didn't exist yet, per the six-touchpoint rule); marked resolved

**One judgment call worth flagging:** the ruling says old slugs aren't migrated, which means the DB may already contain duplicate slugs from before the fix. I did not add a DB-level `UNIQUE` constraint to `docs/contracts/ddl.sql` — that file is legacy schema captured verbatim (P5 rule) and a hard constraint could reject a straight carry-over of pre-existing duplicate rows anyway. Instead I added an `escalation` note on WO-002 directing the executor to enforce uniqueness at the application layer (check-and-suffix at write time), and flagged that this should be re-checked once `docs/migration/` (currently empty — P6 wasn't actually populated in this workspace despite `rebuild.json` marking it complete) defines how legacy `tickets` rows carry over.

**Not touched:** `docs/migration/` population and `backlog.md`/`docs/domain/` — those are pre-existing gaps unrelated to this ruling's blast radius; surfacing them here rather than expanding scope.