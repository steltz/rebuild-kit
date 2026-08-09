# 04 — Notifications: transactional outbox + worker

## The problem being fixed

Legacy `app/notify.py` opens a blocking SMTP connection (`smtp.internal:25`, 30 s timeout)
inside request handlers. During the June SMTP outage, `POST /api/tickets/{id}/close` hung
for up to 30 s per request and then 500'd — closing tickets was effectively down for ~40
minutes. Additionally, legacy commits the close *before* sending, so a failed send loses
the notification forever.

## Requirements

- R1. No request handler ever opens an SMTP connection or waits on one.
- R2. Durable: once a close (or reset request) is committed, its email survives process
  restarts and SMTP outages, and is eventually delivered. At-least-once is acceptable;
  duplicates on retry-after-partial-failure are acceptable (they were impossible to observe
  in legacy only because legacy just dropped mail on failure).
- R3. Ordering across emails is not required.
- R4. No new infrastructure (no Redis/RabbitMQ/Celery). Postgres is already there.

## Design: outbox table + worker loop

Chosen over alternatives:
- **FastAPI `BackgroundTasks` / `asyncio.create_task`** — rejected: in-process, lost on
  crash/redeploy, violates R2.
- **Celery/RQ + broker** — rejected: violates R4; heavy for ~140 emails/period observed.
- **Transactional outbox** — accepted: the enqueue is a plain INSERT in the same DB
  transaction as the state change, so "closed ⇒ notification recorded" is atomic.

### Write path (in request handlers)

Within the same transaction as the ticket close / token creation:

```sql
INSERT INTO outbox_emails (recipient, body) VALUES (:to, :body);
```

Body strings preserve legacy text exactly:
- close: `closed: <title>` to `watchers@example.internal`
- reset: `reset token: <token>` to the requester's email

(Legacy passes these raw strings to `smtplib.sendmail` with no headers — the "email" has no
Subject line. Preserve the body text; adding proper RFC-2822 headers around it is allowed
and recommended — receivers today already tolerate whatever smtp.internal does with raw
bodies. Flagged as Q9 in open questions.)

### Worker (separate process, same codebase)

Entrypoint `python -m app.worker` (or `ticketd-ng worker`). Loop:

1. `SELECT ... FROM outbox_emails WHERE sent_at IS NULL AND next_attempt_at <= now()
   ORDER BY id LIMIT 10 FOR UPDATE SKIP LOCKED` — safe for multiple worker replicas.
2. Send via SMTP (`smtp.internal:25`, sender `ticketd@example.internal`, timeout from
   config, default 30 s — a slow worker hurts nobody now).
3. Success → `sent_at = now()`. Failure → `attempts += 1`, `last_error`, exponential
   backoff `next_attempt_at = now() + least(2^attempts, 3600) * interval '1 second'`.
4. No max-attempts dead-lettering by default: rows just keep retrying hourly; expose
   `attempts` for monitoring. (Simple; revisit if spam risk appears.)
5. Poll interval ~2 s when idle (or LISTEN/NOTIFY later; not required for the observed
   volume of <10 emails/hour).

### Operational notes

- Deploy: run 1 worker process alongside the API (systemd unit / second container command).
- Metrics/verification hook: `SELECT count(*) FROM outbox_emails WHERE sent_at IS NULL AND
  created_at < now() - interval '10 minutes'` should be 0 in steady state; alert if not.
- The June-outage acceptance test (verification V-6): with SMTP unreachable, close 5
  tickets — all return 200 `{"closed": true}` promptly; restore SMTP; all 5 emails deliver
  within 2 backoff cycles.
