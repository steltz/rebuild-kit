# ticketd rewrite workspace

This directory is the complete handoff package for rewriting `ticketd`
(Flask + SQLite → FastAPI + Postgres). It was built by reading the entire
legacy source (`../ticketd/`) and the sampled access log
(`../ticketd/ops/access.log`) — no one was available to answer questions
during this pass, so real open decisions are captured explicitly in
`03-OPEN-QUESTIONS.md` rather than silently guessed at. **Read that file
before executing anything past Phase 1** — several defaults it documents
(especially the slug-collision approach and the `X-Internal-Bypass` header)
are genuine judgment calls a person should confirm, not settled facts.

## Why this rewrite is happening

The June 2026 SMTP outage took ticket-closing down for 40 minutes because
`POST /api/tickets/<id>/close` sends its notification email synchronously,
inside the request. Security also flagged MD5-hashed, plaintext-stored
password-reset tokens. Support keeps hitting slug collisions with no
uniqueness enforcement anywhere. Full detail in
`00-CONTEXT-AND-CONSTRAINTS.md`.

## Reading order

1. **`00-CONTEXT-AND-CONSTRAINTS.md`** — why, what's decided, what's in and
   out of scope, success criteria. Start here.
2. **`01-CURRENT-BEHAVIOR-CONTRACT.md`** — exhaustive, endpoint-by-endpoint
   reverse-engineered spec of what legacy `ticketd` actually does today,
   including the quirks that look like bugs but are load-bearing (most
   important: `GET /api/tickets/<id>` returns `200 {}` for unknown ids, not
   `404` — this is the single easiest thing to accidentally "fix" and break
   the UI with).
3. **`04-TRAFFIC-ANALYSIS.md`** — what the sampled access log actually
   shows, and an explicit warning that it is a single-hour synthetic
   sample, not the real 30-day log the task described.
4. **`DESIGN-architecture.md`** — the new stack's project layout, Postgres
   schema, and endpoint-by-endpoint mapping from legacy to new.
5. **`DESIGN-async-notifications.md`, `DESIGN-password-reset.md`,
   `DESIGN-slug-collisions.md`** — one design doc per named fix, each with
   the options considered and why the recommended approach won.
   `DESIGN-slug-collisions.md` is flagged as a **proposal, not a decision**
   — nobody had settled on an approach before this workspace was built.
6. **`03-OPEN-QUESTIONS.md`** — every place a real decision was made
   unilaterally because no one was around to ask. Read this before Phase 6
   (cutover) at the absolute latest; several items should be resolved
   earlier.

## Executing the rewrite

Plans live in `plans/`, numbered in execution order. Each is a standalone
implementation plan in the format expected by
`superpowers:subagent-driven-development` / `superpowers:executing-plans` —
open a plan file and use one of those skills to run it task-by-task, with
review checkpoints between tasks.

| Phase | File | Depends on |
|---|---|---|
| 0 | `plans/00-project-setup.md` | — |
| 1 | `plans/01-schema-and-migration.md` | 0 |
| 2 | `plans/02-core-tickets-api.md` | 1 |
| 3 | `plans/03-async-notifications.md` | 2 (implements the SMTP-outage fix) |
| 4 | `plans/04-secure-password-reset.md` | 3 (reuses the outbox) |
| 5 | `plans/05-export-and-polish.md` | 4 |
| 6 | `plans/06-migration-and-cutover.md` | 0-5, **human-supervised — real data and real cutover timing, not something to run unattended** |

Each phase's plan document names its own dependencies and links back to the
specific behavior-contract/design sections it implements — you shouldn't
need to hold the whole workspace in your head to execute any single phase,
but Phase 0 and `01-CURRENT-BEHAVIOR-CONTRACT.md` are required reading
before any of them.

## Verification

`verification/VERIFICATION.md` describes the full strategy. Two runnable,
dependency-light scripts back it:

- `verification/parity_check.py` — replays requests against a running
  legacy instance and a running new instance and diffs the responses.
- `verification/smtp_outage_test.py` — the direct regression test for the
  incident that started this project: points the new API at an
  unreachable SMTP target and asserts close-request latency stays flat
  anyway.

Both were syntax-checked (`python3 -m py_compile`) but not run end-to-end in
this workspace, since that requires a running instance of the (not yet
built) new API — they're meant to be run for the first time during Phase 2
(parity) and Phase 3 (SMTP outage) respectively, once there's something to
run them against.

## What's genuinely unresolved (see `03-OPEN-QUESTIONS.md` for full detail)

1. The access log is a single-hour synthetic sample, not a real 30-day
   capture — get the real one before capacity planning.
2. The slug-collision fix (numeric suffix on collision) is a proposed
   default, not an approved decision.
3. Whether changing the on-the-wire timestamp format (to fix the
   naive-local-time bug) counts as an out-of-scope "UI change."
4. What the undocumented `X-Internal-Bypass` header on the reset endpoint
   is for, and whether it should survive the rewrite as-is.
5. Whether `GET /internal/export/csv` (zero traffic in the sample log) is
   worth keeping.
6. Whether the unused `assignee_id` column hints at a planned feature.
7. Whether `ticketd` sits behind an authenticating gateway in production —
   the API itself has no auth of its own, and the rewrite preserves that
   assumption without being able to confirm it.
8. Postgres hosting, backups, and secrets management per environment —
   entirely unaddressed here; `plans/00-project-setup.md` only covers local
   dev via Docker Compose.

## Directory contents

```
rewrite/
  README.md                          - this file
  00-CONTEXT-AND-CONSTRAINTS.md      - why, scope, success criteria
  01-CURRENT-BEHAVIOR-CONTRACT.md    - reverse-engineered legacy behavior spec
  03-OPEN-QUESTIONS.md               - decisions made unilaterally; flag for review
  04-TRAFFIC-ANALYSIS.md             - what the access log shows (and its limits)
  DESIGN-architecture.md             - new stack layout, schema, endpoint mapping
  DESIGN-async-notifications.md      - fixes the SMTP outage (outbox + worker)
  DESIGN-password-reset.md           - fixes the MD5 token finding
  DESIGN-slug-collisions.md          - proposed fix for slug collisions (unapproved)
  plans/
    00-project-setup.md
    01-schema-and-migration.md
    02-core-tickets-api.md
    03-async-notifications.md
    04-secure-password-reset.md
    05-export-and-polish.md
    06-migration-and-cutover.md
  verification/
    VERIFICATION.md
    parity_check.py
    smtp_outage_test.py
```
