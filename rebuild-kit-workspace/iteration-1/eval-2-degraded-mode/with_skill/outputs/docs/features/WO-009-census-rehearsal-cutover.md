# WO-009 — Census execution, migration rehearsal, cutover (GATED × 2)

id: WO-009            depends_on: [WO-008]    milestone: M3
risk: 0.75 (touches production data; every upstream unknown lands here; currently
  unstartable)          gate: true (rehearsal sign-off AND cutover sign-off)
status_note: blocked_by_asks: [OQ-INT-2] — requires production DB access (ETA "a few weeks")
usage_weight: n/a   pain_weight: n/a
context_budget: ~300 lines (this WO + docs/migration/* + gate packets)

steps (each produces evidence for the next):
  1. Run docs/migration/census-queries.sql read-only against prod-shaped data (adapt
     dialect — source is SQLite); record counts + scrubbed samples in census.md.
     [spec-patch: rerun of P6 with data_census flipped active in rebuild.json]
  2. Owner ratifies every ASK policy in mapping.md (TZ, dangling assignees, enum strays,
     token carry, rollback window) — rulings appended to open-questions.md.
  3. Full dry run on a production snapshot: transform → reconciliation green → twin-boot
     modern against the migrated snapshot and run the FULL core replay set. GATE: rehearsal
     sign-off (packet: guide/briefs/gate-M3-rehearsal.md).
  4. Cutover per mapping.md sequence (stop writes → delta → reconcile → repoint → legacy DB
     read-only for the ratified rollback window). GATE: cutover sign-off
     (packet: guide/briefs/gate-M3-cutover.md).

acceptance:
  replay_set: full core.jsonl green against the migrated snapshot (step 3)
  tests: reconciliation R1-R8 green on the real snapshot
escalation: none
