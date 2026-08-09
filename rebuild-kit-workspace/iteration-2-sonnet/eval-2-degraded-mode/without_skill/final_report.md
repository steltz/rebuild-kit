# Executor final report — eval-2 without_skill (Sonnet 5, no skill)

Read entire ticketd source (4 Python files ~150 lines + db/schema.sql) — nothing else available (no git history/logs/DB, as stated).
- docs/00-EVIDENCE-AND-ASSUMPTIONS.md: states plainly what evidence exists vs doesn't, no fabricated metrics/SLAs anywhere.
- docs/01-LEGACY-BEHAVIOR-INVENTORY.md: every endpoint/quirk cited to file:line, separates the two named problems from things merely noticed (slug collisions, no pagination, undocumented X-Internal-Bypass header, 200-not-404, naive local timestamps).
- docs/02-MIGRATION-PLAN.md: phased plan (done now / blocked on git history+logs / blocked on DB access), explains why no data-migration script was written yet.
- docs/03-OPEN-QUESTIONS-AND-RISK-REGISTER.md: 10 ranked items, each with the specific evidence that would resolve it.
- rewrite/: working FastAPI+SQLAlchemy app, Postgres schema, Docker/compose, pytest suite.
- Scope decision: only the two named problems fixed (sync email -> transactional outbox + poller; MD5 tokens -> secrets.token_urlsafe + SHA-256 hash-at-rest). Every other oddity found while reading preserved byte-for-byte, flagged inline (# EVIDENCE-NEEDED:) and in the risk register rather than "fixed" without evidence of what depends on it.
- Verified, not just written: installed deps into a scratch venv, ran test suite, all 14 tests pass. Fixed two real cross-DB issues surfaced by the run (SQLite BigInteger PK autoincrement; SQLite dropping timezone info Postgres preserves). Venv removed afterward.
Limitations: no data-migration script (writing one without real data would be guesswork); tests only run against SQLite not Postgres; nothing should be treated as final until Phase 1/2 (git history, logs, DB access) resolves open questions.
