# ticketd rewrite workspace

This directory is the complete working kit for rewriting `../ticketd` (Flask 1.x + SQLite,
running since 2019) onto **FastAPI + PostgreSQL**. It is written so that future Claude Code
sessions can execute the rewrite without the original stakeholders present.

## Read in this order

1. `specs/00-overview.md` — why we are rewriting, goals, hard scope boundaries.
2. `specs/01-legacy-inventory.md` — every observable behavior of the legacy app, each tagged
   **PRESERVE / CHANGE / DROP / DECIDE**. This is the source of truth for compatibility.
3. `specs/02-api-contract.md` — the target API, endpoint by endpoint, with exact
   request/response shapes.
4. `specs/03-data-model.md` — target Postgres schema and the SQLite → Postgres migration.
5. `specs/04-notifications.md` — async notification design (the June SMTP outage fix).
6. `specs/05-security-reset.md` — password-reset token redesign (the MD5 finding).
7. `plan/implementation-plan.md` — phased plan with tasks, dependencies, and per-phase
   definition of done.
8. `verification/verification.md` — acceptance checklist and how to run the contract tests
   in `verification/contract_tests/` against legacy and new implementations.

Supporting material:

- `decisions/open-questions.md` — **read before starting any phase.** Questions we could not
  answer during workspace setup, each with a default recommendation. If stakeholders are
  still unavailable, follow the recommendation and record what you did in that file.
- `analysis/access-log-findings.md` — measured traffic from `../ticketd/ops/access.log`,
  used to justify preserve/drop calls.

## Ground rules (from leadership sign-off)

- Stack is **decided**: FastAPI + Postgres. Do not relitigate.
- **No UI changes** are in scope. The only client observed is `svc-ui/2.1`; the new API must
  be a drop-in replacement for every request shape the UI sends today (see the contract).
- The three known problems that motivated the rewrite, in priority order:
  1. Synchronous in-request SMTP (took ticket-closing down for 40 min in June).
  2. MD5 password-reset tokens stored in plaintext in a bare table (security finding).
  3. Slug collisions on similarly-named tickets (**fix not yet decided** — see
     `decisions/open-questions.md` Q1; the schema and plan carry a gated task for it).

## Where the new code goes

Create the new service in a sibling directory `../ticketd-ng/` (keep `../ticketd/` untouched
as the reference implementation while contract tests compare the two). Suggested layout is in
`plan/implementation-plan.md`, Phase 0.
