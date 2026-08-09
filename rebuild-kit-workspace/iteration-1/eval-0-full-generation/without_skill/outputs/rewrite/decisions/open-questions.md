# Open questions & decisions needed

We (the workspace authors) could not reach stakeholders during setup. Each question has a
**default recommendation**; if nobody has answered by the time a phase needs the decision,
implement the default and record it here (fill in the "Resolution" line). Questions are
ordered by how much they block.

---

## Q1 — Slug collision fix (BLOCKS Phase 2 finalization) — *the undecided one from the brief*

Support keeps hitting collisions ("Fix DB" vs "fix db!" → `fix-db`). Nobody has decided the
fix. Options:

| Option | Behavior | Cost |
|---|---|---|
| A. Suffix on collision | `fix-db`, `fix-db-2`, `fix-db-3` (unique index + retry loop) | Slug no longer a pure function of title; existing duplicate slugs in legacy data must be renumbered during migration **or** the unique index applies to new rows only |
| B. Random suffix always | `fix-db-x7k2` | All new slugs look different from old ones; ugliest |
| C. Id-based slug | `42-fix-db` | Guaranteed unique, but changes the slug returned for every new ticket |
| D. Keep colliding (status quo) | No change | Support pain continues; rewrite ships a known bug |

**Recommendation: Option A** — closest to current behavior, collision-free going forward.
Migration renumbers legacy duplicates (keep the oldest ticket's slug, suffix newer ones)
and logs every rename. Risk: if anything deep-links by slug it could break — we found no
evidence any API endpoint even accepts slugs (lookup is by id only), so slug appears to be
display-only, which makes A safe.
The plan gates task 2.6 and migration step on this. **Resolution:** _(pending)_

## Q2 — Keep the `X-Internal-Bypass` rate-limit bypass header?

Undocumented; headers aren't in the access log, so we cannot tell if anything uses it.
**Recommendation:** implement it behind config `RESET_RATE_BYPASS_ENABLED` (default
**false**). If something internal breaks at cutover, flipping the flag restores legacy
behavior without a deploy. Ask security whether it should exist at all.
**Resolution:** _(pending)_

## Q3 — Confirm dropping `GET /internal/export/csv`

0 hits in the provided log; code comment says no caller since the 2020 audit.
**Recommendation:** do not implement; keep this note so that if an annual audit script
appears (the log window may simply not include audit season), it can be re-added in a day —
with proper CSV escaping this time. **Resolution:** _(pending)_

## Q4 — Who consumes `POST /api/auth/reset/confirm`'s `{"email": ...}`?

There is no login endpoint and no password column; confirm's success response hands an
email to *someone* (20 calls in the log window, so it is live — presumably an upstream
auth/SSO flow, likely via the same gateway that authenticates users, since every log line
carries an authenticated corporate email). We preserved the contract exactly.
**Need from stakeholders:** identity of the caller, so it can be pointed at the new host at
cutover and included in smoke tests. **Resolution:** _(pending)_

## Q5 — Timestamp serialization at cutover

Legacy emits naive **local-time** ISO strings. New storage is UTC.
**Recommendation:** serialize naive-UTC (same string shape, values shift by the host's UTC
offset once). Most UIs treat these as opaque or parse-and-display; a shift is visible only
around the cutover. Alternative if svc-ui displays raw strings: serialize in the legacy
host's timezone (config `DISPLAY_TZ`). Also need the legacy host's timezone for the data
migration (`--source-tz`). **Need from stakeholders:** legacy host TZ, and whether svc-ui
parses or displays timestamps raw. **Resolution:** _(pending)_

## Q6 — Invalid `priority` values: legacy 500s (SQLite CHECK), new returns 422 `invalid_priority`

We chose the clean 422 deliberately (a 500 was never a *usable* contract). If someone
insists on bug-for-bug, it's a one-line change. **Resolution:** _(pending — default 422)_

## Q7 — Deployment details

Port (legacy: 5000), process supervisor, where Postgres lives, secrets management for the
DB URL, whether the gateway needs config changes at cutover. None of this blocks
implementation (everything is 12-factor config); it blocks Phase 6 cutover.
**Resolution:** _(pending)_

## Q8 — Production SQLite file access

`db/ticketd.sqlite3` is not in the repo. The migration script needs the real file (and the
host TZ, Q5) at cutover. **Resolution:** _(pending)_

## Q9 — Email format

Legacy sends raw bodies with no Subject/headers via `smtplib.sendmail`. We preserve the
body text but recommend wrapping in a proper MIME message with a Subject (`[ticketd]
ticket closed` / `[ticketd] password reset`). Confirm receivers (watchers list, and
whatever parses reset mails — likely humans) are fine with headers appearing.
**Recommendation:** proper MIME, same body text. **Resolution:** _(pending)_

## Q10 — The ~2.5% 500-rate in the access log

51 of 2000 logged requests returned 500, spread across ticket endpoints (31 GET list, 12
POST create, 3 GET by-id, 5 close). Cause unknown — could be SQLite lock contention under
concurrency (SQLite + multi-threaded Flask is a classic source). Postgres likely fixes it
for free, but nobody has confirmed the cause. Not blocking; noted so the parity suite does
NOT try to reproduce 500s, and so cutover monitoring watches the 500-rate drop.
**Resolution:** _(pending)_
