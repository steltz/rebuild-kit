# Executor final report — eval-2 without_skill (baseline, no skill)

Produced outputs/rewrite/ with docs + working code; handed-over ticketd/ untouched (test runs used scratch copies).
- README: every claim tagged [S] source-verified (file:line), [H] handover note, [A] assumption, [U] unknown.
- inventory/behavior-inventory.md: endpoint-by-endpoint contract with 12 numbered quirks (Q1–Q12).
- inventory/dead-code-and-unknowns.md: CSV export, legacy_import.py, never-touched users/assignee_id; load-bearing unknown: no passwords stored, unknown consumer of reset/confirm — shape frozen.
- decisions/ADR-001..004: outbox async email, CSPRNG+hashed tokens (found MD5 token is md5(email+time) i.e. predictable), bug-for-bug wire compat with config flags, Postgres schema/timezone policy.
- evidence/intake-checklist.md (A1–A6 logs, B1–B5 git, C1–C7 prod DB with SQL, D1–D4 people); evidence/evidence-log.md append-only.
- app/: runnable FastAPI scaffold (SQLAlchemy 2 + psycopg): wire-compatible routers, outbox + worker, token service. sql/001_initial.sql Postgres schema. migration/ plan + script with per-row savepoint quarantine; refuses to run without explicit --legacy-tz.
- tests/test_parity.py: 29 black-box characterization tests runnable against either implementation.
Verification: parity vs live legacy scratch copy 24 passed / 5 xfailed (SMTP paths); vs rewrite all 29 passed. Bonus: legacy defect L1 — unclosed SQLite connections cause intermittent "database is locked" 500s.
Limitations: rewrite verified on SQLite stand-in not Postgres; legacy characterized under modern Flask; all usage-evidence questions open; LEGACY_TZ placeholder.
