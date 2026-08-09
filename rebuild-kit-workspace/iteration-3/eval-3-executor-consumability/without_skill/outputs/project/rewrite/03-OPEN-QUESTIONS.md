# Open questions

This workspace was built without access to anyone who could answer
questions live, per the task instructions. Every item below is a real
decision point where I made a default assumption so the plan is still
executable — but a human should confirm or override each one, ideally
**before** the relevant plan phase runs, and at the latest before cutover.
Each item says what the default is, why, and what the blast radius of being
wrong is.

## 1. The access log is not actually a 30-day log — get the real one

**Finding:** `ticketd/ops/access.log` covers a single 60-minute window on a
single date with a single client identity, not 30 days (see
`04-TRAFFIC-ANALYSIS.md` for the evidence). It's useful for endpoint mix and
confirming the general error shape, but it is not a real capacity baseline
and it does not contain evidence of the June outage itself.

**Default used in this workspace:** treat the endpoint-mix ratios as
directional only; don't derive SLOs, worker pool sizes, or rate limits from
raw counts in this file.

**Ask:** pull the actual 30-day (or longer) production access/error log
before finalizing capacity planning, worker concurrency, or Postgres sizing
in `plans/06-migration-and-cutover.md`. If a real SMTP-outage window exists
in that log, it's worth looking at directly — it would show whether close
requests queued up, timed out, or were dropped client-side, which tells you
whether the outbox worker's poll interval (proposed: 5s) is fast enough.

## 2. Slug collision fix — approach is proposed, not approved

**Default used:** numeric suffix on collision (`fix-db`, `fix-db-2`, ...),
enforced via a Postgres unique index + retry-on-conflict. Full rationale and
two rejected alternatives (id-suffix-always, random-suffix) in
`DESIGN-slug-collisions.md`.

**Ask:** does product/support have a preference here, or an existing
convention elsewhere in the company for disambiguating human-readable slugs?
Also: should the handful of *already-colliding* slugs in the current SQLite
data be disambiguated during migration, or left alone? Default used:
leave alone (renumbering historical slugs could break existing bookmarked
links, which seems worse than a handful of old tickets sharing a slug).

**Blast radius if wrong:** low-to-medium. This is isolated to
`app/services/slugs.py` (see `DESIGN-architecture.md`) — changing the
suffixing scheme later is a small, contained change, not a rearchitecture.

## 3. Timestamp format on the wire

**Finding:** legacy timestamps are naive local server time with no offset —
a real bug (`# naive local time!` in the source), but it's also the exact
string shape the UI has always received.

**Default used:** store correctly (Postgres `TIMESTAMPTZ`, UTC internally)
but don't decide the API's serialized output format as part of this
rewrite — route it through one shared formatting function
(`format_legacy_timestamp()`, see `DESIGN-architecture.md`) so the decision
can be made and applied in one place instead of being scattered across
routes.

**Ask:** is changing the literal timestamp string the UI receives (e.g. to
add a UTC offset) considered "a UI change" for purposes of this rewrite's
"no UI changes" constraint, even though no UI code is touched? If the UI
already does its own timezone math assuming naive local time, switching to
offset-aware strings could visibly shift displayed times. Needs a real
answer from whoever owns the frontend, not a guess baked into the backend.

## 4. The `X-Internal-Bypass: 1` header on `/api/auth/reset`

**Finding:** an undocumented header that fully bypasses the reset
rate-limit, no other auth. No comment in the code explains who sets this or
why.

**Default used:** preserved as-is (same header name, same bypass semantics)
for compatibility, since removing it silently could break whatever
internal service currently relies on it (a QA harness? an admin tool? a
support runbook?).

**Ask:** who/what sets this header today, and why does it need to bypass
rate limiting entirely rather than authenticating some other way? This is a
security-relevant undocumented backdoor and is worth a real decision (keep
as-is / replace with a proper internal-service credential / remove) rather
than carrying it forward on autopilot. Flagging prominently rather than
silently preserving because "preserve legacy behavior" is the wrong default
specifically when the legacy behavior is an unauthenticated bypass no one
can currently explain.

## 5. `GET /internal/export/csv` — keep or drop?

**Finding:** comment says "written for the 2020 audit; no caller since,"
and the sampled access log confirms zero requests to it.

**Default used:** carry it forward in `plans/`, but as a low-priority,
easily-droppable item — see `plans/02-core-tickets-api.md`. Cheap to keep,
so defaulting to "keep" rather than deleting something without being asked
to.

**Ask:** does anyone still use this for audit purposes? If genuinely dead,
dropping it is a nice small cleanup, but that's a call for whoever owns
compliance/audit needs, not an engineering-only decision.

## 6. `assignee_id` — dead column or a hint of a feature to come?

**Finding:** the column exists in the schema, references `users`, but no
endpoint reads or writes it. No evidence in the code or the access log that
assignment is a live feature.

**Default used:** carry the column forward for schema parity (cheap, low
risk), but do **not** build any assignment feature around it — that would be
scope creep beyond the three named fixes.

**Ask:** is ticket assignment a planned feature that got scaffolded and
never finished, or genuinely vestigial? Doesn't block the rewrite either
way, just worth knowing so nobody's surprised the column exists with no
behavior behind it.

## 7. Does `ticketd` sit behind an authenticating proxy/gateway?

**Finding:** the API itself has zero authentication/authorization anywhere.
The access log shows a single identity (`jdoe@corp.example.com`) attributed
to every request, which reads like a gateway is annotating requests with an
already-authenticated identity rather than `ticketd` doing its own auth —
but the log's other quirks (single client, single hour, see open question 1)
mean this can't be confirmed from the log alone.

**Default used:** the rewrite adds no authentication of its own (matching
legacy exactly) and assumes nothing about what fronts it.

**Ask:** confirm whether production traffic to `ticketd` really does pass
through an authenticating gateway/proxy that the new service can continue to
assume sits in front of it, especially since the network topology may change
as part of moving to a new stack/deployment target.

## 8. Postgres hosting / ops ownership

Not addressed anywhere in this workspace: who runs the Postgres instance
(managed service vs. self-hosted), backup policy, and where secrets (SMTP
credentials, DB URL) come from in each environment. `plans/00-project-setup.md`
stubs this with placeholders — needs real values before deploying anywhere
past local dev.
