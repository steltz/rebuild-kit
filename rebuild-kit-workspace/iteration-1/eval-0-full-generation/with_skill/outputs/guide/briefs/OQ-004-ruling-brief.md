# Ruling needed: OQ-004 — Email dispatch mechanism for the PB-001 repair

**What's being decided.** The *outcome* is ratified (mail must never block or fail a
request — that's the rewrite's founding purpose). The *mechanism* is a preference we
couldn't ask about.

**Why it's flagged.** The generator defaulted to a Postgres transactional outbox
(`mail_outbox` in `docs/migration/target-schema.sql`) + a delivery worker: no new
infrastructure, atomic with the triggering write, at-least-once delivery. If your team
already runs a queue (Redis/RabbitMQ/SQS...), you may prefer it for operational
consistency.

**Where it bites.** WO-004 (M1) builds it; WO-005 reuses it. Not blocking — WO-004
proceeds with the default as a recorded FREE choice; a later ruling redirects via
spec-patch (cost grows after M1).

**Options & consequences.**
1. Transactional outbox + worker (default) → one more table + one worker process to run;
   exactly-once-ish semantics come free with the DB transaction.
2. Existing queue infra → operational familiarity; loses transactional atomicity with the
   commit unless an outbox still fronts it.
3. FastAPI BackgroundTasks → zero infra, but mail dies with the process — weakest; not
   recommended for the defect that caused this rewrite.

**Recommendation (non-binding).** Option 1 unless a queue you already operate says
otherwise. Rule before WO-004 starts (early M1).

---
Ruling: ____________  Ruled by: ________  Date: ______
