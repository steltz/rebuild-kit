# Design: async notifications (fixes the June SMTP outage)

## The problem, precisely

`app/notify.py`:
```python
def send_mail(to, body):
    with smtplib.SMTP("smtp.internal", 25, timeout=30) as s:
        s.sendmail("ticketd@example.internal", [to], body)
```
called synchronously from inside `POST /api/tickets/<id>/close` (and
`POST /api/auth/reset`), after the DB commit. When SMTP is slow or down,
every caller blocks up to 30s holding a request worker. At sustained close
volume, workers saturate and the API stops being able to close tickets at
all — even though closing a ticket has nothing to do with email delivery
once you say it out loud. That mismatch (a core write operation being
gated on a notification side-effect) is the actual bug; "make email faster"
is not a fix, only a delay of the same failure mode.

## Options considered

1. **FastAPI `BackgroundTasks`.** Runs the send after the response is
   returned, in the same process. Rejected as the primary mechanism: it
   removes the *latency* problem but not the *durability* problem — if the
   worker process restarts/redeploys/crashes between "response sent" and
   "email actually sent," the notification is silently lost, and a
   sustained SMTP outage still means a growing pile of in-flight background
   tasks inside the same process that's trying to serve HTTP traffic (no
   backpressure, no retry, no visibility). Doesn't need new infra, but
   doesn't actually solve durability.
2. **External queue (Celery/RQ/arq + Redis, or SQS).** Solves durability and
   retry well, but introduces a new infrastructure dependency the team
   doesn't currently run, purely to move ~100-150 emails/hour (per the
   sampled traffic). Disproportionate for this system's actual volume.
3. **Transactional outbox in Postgres + standalone poller worker.**
   (Recommended, and what `DESIGN-architecture.md` assumes.) The `close`
   (or `reset`) handler writes both the ticket update and a
   `notification_outbox` row in the **same DB transaction** — so "the
   ticket is closed" and "an email is queued to be sent" become atomic; you
   can't get one without the other, unlike the current code where the ticket
   commits and *then* email is attempted as a separate, failure-prone step.
   A separate `worker.py` process polls `notification_outbox` for
   `sent_at IS NULL` rows, attempts delivery, and marks them sent or bumps
   `attempts`/`last_error` on failure. No new infra (Postgres is already the
   datastore); durable across restarts of either process; retryable;
   observable via a normal SQL query (`SELECT count(*) FROM
   notification_outbox WHERE sent_at IS NULL AND attempts > 0` is your
   "is email backed up" dashboard metric for free).

**Recommendation: option 3.** This is encoded as the default in
`plans/03-async-notifications.md`. It directly fixes the outage mechanism
(SMTP being down can no longer block a close request, full stop — the
request's only dependency is Postgres, which was already a hard dependency)
and it's a strict improvement on today's failure semantics (see behavior
contract §`POST /api/tickets/<id>/close` — today, an SMTP failure can 500 a
request whose write already committed; with the outbox, the request never
even attempts SMTP, so it can't fail because of it).

## Worker behavior (specification, not just architecture)

- Poll interval: 5s (configurable). At the sampled traffic's volume this is
  more than fast enough; email notification was never a hard-real-time
  requirement, and 5s beats "up to 30s + possible total outage" by a wide
  margin regardless.
- Batch size per poll: 50 rows (`SELECT ... WHERE sent_at IS NULL ORDER BY
  created_at LIMIT 50 FOR UPDATE SKIP LOCKED`) — the `SKIP LOCKED` matters
  if more than one worker instance ever runs; harmless with one.
- On success: `UPDATE notification_outbox SET sent_at = now() WHERE id = ?`.
- On failure: `UPDATE ... SET attempts = attempts + 1, last_attempt_at =
  now(), last_error = ? WHERE id = ?`. Retry with backoff:
  skip rows whose `last_attempt_at` is within `min(2^attempts, 300)`
  seconds — i.e. 2s, 4s, 8s, ... capped at 5 minutes between retries.
- Give up after 10 attempts (leaves the row with `sent_at IS NULL`,
  `attempts = 10`, visible forever for manual triage — do not delete failed
  rows). This is a deliberate, simple policy; revisit only if real volume
  data says otherwise.
- The worker must not crash the process on a single bad row — catch, record
  `last_error`, move to the next row.
- Deployment: the worker is a separate long-running process
  (`python -m app.worker`), run under whatever the team already uses for
  long-running processes (systemd unit / supervisor / k8s Deployment — same
  answer as "how do we run the API," not a new pattern). It has no HTTP
  surface and needs no load balancer.

## What does NOT change

`send_mail()`'s actual SMTP call (`app/notify.py`) can be reused almost
verbatim inside the worker — the fix is about *where* and *when* it's
called, not how it talks to SMTP. Keep the 30s timeout (it's now the
worker's problem, not a request's).
