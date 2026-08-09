# ADR-001: Notifications via transactional outbox, not in-request SMTP

Status: accepted (safe from source alone). Date: 2026-08-08.

## Problem

Legacy sends email synchronously inside request handlers (`notify.py:6`, called from
`server.py:76,94`) with a 30s SMTP timeout. Handover names this as problem #1. Source
shows the worse consequence (Q10): on close-ticket, the DB commit happens *before* the
send, so an SMTP outage yields a 500 with the ticket already closed and the
notification permanently lost (retries see `{"closed": false}` and never send).

## Decision

Write every outgoing email as a row in an `outbox_emails` table **in the same
transaction** as the state change that caused it. A separate worker process
(`app/workers/outbox_worker.py`) polls the table, sends via SMTP, marks rows sent, and
retries failures with a capped attempt count.

Rejected alternatives:
- **FastAPI BackgroundTasks** — in-process, lost on crash/restart, no retry; solves
  latency but not reliability.
- **Real broker (Celery/RQ/etc.)** — more moving parts than a two-table internal tool
  justifies; can be introduced later without changing the enqueue contract.

## Behavior changes (deliberate, must be communicated)

1. Close-ticket and reset requests no longer block on SMTP and no longer 500 on SMTP
   failure. If any client *relied* on the 500 (unknown, `[U]`, see intake A6), this is
   a break.
2. Emails become at-least-once with delay, instead of at-most-once immediate.
3. Legacy sends header-less payloads (envelope only). The worker reproduces that
   verbatim by default (`SMTP_LEGACY_HEADERLESS=true`) until a captured production
   email tells us what recipients actually expect (intake D-list item 7 in
   `../inventory/dead-code-and-unknowns.md`).
