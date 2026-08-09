# ticketd rewrite workspace

Target: FastAPI + Postgres rewrite of `../ticketd` (Flask 1.x + SQLite, in production since 2019).

## Evidence status: DEGRADED

This workspace was generated from **source code and two handover notes only**. We have:

- NO git history
- NO access logs
- NO production database access (expected in a few weeks)

Every claim in this workspace is tagged with its evidence level:

| Tag | Meaning |
|-----|---------|
| `[S]` | Verified by reading the legacy source (file:line cited) |
| `[H]` | Stated in the handover notes |
| `[A]` | Assumption made to keep moving; must be validated |
| `[U]` | Unknown; blocked on evidence we don't have yet |

**Rule for this rewrite:** where behavior is `[S]` we preserve it bug-for-bug behind
compat flags unless a decision record says otherwise. Where a claim is `[A]` or `[U]`,
the scaffold takes the conservative path (preserve legacy behavior, gate changes behind
config) and the item appears in `evidence/intake-checklist.md` so it gets resolved the
moment history/logs/DB arrive. Nothing in here should be read as "confirmed usage data".

## Layout

```
rewrite/
  inventory/
    behavior-inventory.md      Every endpoint and behavior of legacy ticketd, quirks included
    dead-code-and-unknowns.md  Dead-code candidates and things the source cannot tell us
  evidence/
    evidence-log.md            Append-only log of evidence as it arrives (currently: source + handover only)
    intake-checklist.md        Exactly what to pull from git history / access logs / prod DB, and which
                               open decision each item unblocks
  decisions/
    ADR-001 .. ADR-004         Decisions already safe to make from source alone
  app/                         Runnable FastAPI scaffold (see app/README.md)
  sql/001_initial.sql          Postgres schema (legacy-shaped + outbox table)
  migration/
    data-migration-plan.md     SQLite -> Postgres plan, with the open timestamp question
    migrate_sqlite_to_postgres.py
  tests/
    test_parity.py             Black-box characterization tests; run the SAME suite against
                               legacy and the rewrite via TICKETD_BASE_URL
```

## The two known problems (handover) and how the scaffold addresses them

1. **Synchronous email in requests** `[H]`, confirmed `[S]` at `ticketd/app/notify.py:6`
   (30s SMTP timeout on the request thread) and call sites `server.py:76,94`.
   → Fixed via a transactional **outbox table + worker** (ADR-001). Note this
   deliberately changes failure semantics; see ADR-001 "behavior change".

2. **MD5 password-reset tokens** `[H]`, confirmed `[S]` at `server.py:90` — worse than
   stated: the token is `md5(email + time.time())`, i.e. *predictable*, not just weakly
   hashed. → Replaced with `secrets.token_urlsafe(32)`, stored hashed (ADR-002).

## Suggested order of work

1. Read `inventory/behavior-inventory.md` end to end.
2. Skim the ADRs; veto anything you disagree with before code hardens around it.
3. Stand up the scaffold (`app/README.md`) against a scratch Postgres.
4. Run `tests/test_parity.py` against a locally-run copy of legacy ticketd, then against
   the rewrite; diff the failures.
5. When evidence access arrives, work through `evidence/intake-checklist.md` top to
   bottom and update `evidence/evidence-log.md` as you go.
