# Open questions — to resolve once we have access logs / prod DB access

Everything here was deliberately **not** decided during the autonomous
scaffolding run, because deciding it would mean guessing at evidence we
don't have. Each item has: what we'd change, and what evidence would let
someone (human or agent) make the call.

1. **`GET /api/tickets/<id>` — `200 {}` vs. `404` on missing ticket.**
   Legacy comment claims the UI depends on the current behavior. If access
   logs show no client actually branches on status code (only on body
   shape), switch to a real `404`. *Evidence needed*: request logs showing
   how callers handle this response, or the frontend source if it turns up.

2. **`X-Internal-Bypass: 1` header.** Currently unauthenticated — anyone who
   knows the header name bypasses reset rate-limiting. Carried forward as-is
   in this rewrite (see `DESIGN.md`) because we don't know who depends on it.
   *Recommended fix once evidence exists*: replace with a real service-to-
   service credential (mTLS, signed JWT, or at minimum a secret API key
   checked against an env var) scoped to whatever internal service needs the
   bypass. *Evidence needed*: access logs showing which source IPs/services
   send this header today, and why.

3. **Slug collisions.** No uniqueness enforcement, matches legacy. If real
   data shows collisions are actually causing problems (e.g., URL routing
   ambiguity), consider `slug` + numeric suffix or making `(slug)` non-unique
   by design and routing by `id` only. *Evidence needed*: query prod data for
   duplicate slugs once DB access exists.

4. **CSV export endpoint (`/internal/export/csv`).** Comment says "no caller
   since [the 2020 audit]." Ported as-is (cheap to keep), but worth
   confirming it's actually unused before assuming it's safe to remove
   later. *Evidence needed*: access logs — any hits at all in the observation
   window.

5. **`legacy_import.py`.** Not ported (see `AUDIT.md` scope boundary). If
   evidence turns up (e.g., someone finds a cron job or runbook that still
   invokes it), it's a small isolated addition — a script + a one-time CLI
   command, not a route.

6. **Outbox worker vs. real message broker.** The rewrite uses a Postgres
   outbox table + in-process poller instead of assuming Celery/RQ/SQS exist.
   *Evidence needed*: what infra is actually available in production, and
   real notification volume. If volume is high or multi-replica coordination
   becomes a problem, promote `NotificationBackend` to a proper queue-backed
   implementation — the interface is already isolated for that swap.

7. **`users` table provisioning.** Nothing in the legacy codebase writes to
   `users`. Rewrite doesn't add a user-creation endpoint either, to avoid
   guessing at auth/provisioning that might already happen elsewhere (SSO
   sync? admin console? direct SQL?). *Evidence needed*: find out how users
   currently get into that table before designing anything here.

8. **Naive local time → UTC.** Treated as a safe storage-layer fix (see
   `DESIGN.md`) since the API contract (ISO 8601 string) doesn't change. Flag
   here only in case some client parses the string and assumes local time
   with no offset — worth a quick log/code check once evidence exists.

9. **Reset-token retention.** Legacy never expires/deletes old rows except on
   successful confirm — expired-but-unconfirmed tokens accumulate forever.
   Rewrite carries this forward (no cleanup job added) since it's a storage
   hygiene issue, not a functional one, and adding a cleanup job is a design
   decision (schedule? TTL index?) better made with real volume data.
   *Evidence needed*: row count growth rate in `reset_tokens` /
   `outbox_messages`.

10. **Rate limit scope.** Legacy rate-limits by `email` only (not IP). Carried
    forward as-is. Worth revisiting once we can see abuse patterns, if any.
