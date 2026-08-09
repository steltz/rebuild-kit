# ticketd rewrite — Phase 3: Async Notifications + Close Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Depends on:** Phase 2 (`02-core-tickets-api.md`) complete.
> **Read first:** `../DESIGN-async-notifications.md` in full — this phase
> is a direct implementation of that design, including the retry/backoff
> policy. Do not improvise a different policy; the numbers there
> (5s poll, 50-row batch, exponential backoff capped at 5 min, give up
> after 10 attempts) are the spec, not examples.

**Goal:** Implement `POST /api/tickets/{id}/close` so it never blocks on
SMTP — the fix for the incident that triggered this whole rewrite — via a
transactional outbox + standalone worker process.

**Architecture:** `close_ticket` writes the status change and a
`notification_outbox` row in one DB transaction, then returns immediately.
A separate `app/worker.py` process polls the outbox and does the actual
SMTP send, with retry/backoff, entirely decoupled from request handling.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, `smtplib` (ported from
legacy `app/notify.py`), plain polling loop (no new infra).

## Global Constraints

- `POST /api/tickets/{id}/close` must not call SMTP directly, ever, under
  any code path.
- Response shape for `close` is unchanged from legacy: `{"closed": bool}`.
  `true` only when this call transitioned the ticket; `false` for
  already-closed or unknown ids (no distinction between those two cases —
  see behavior contract).
- The worker must be runnable and testable independently of the API
  process (no shared in-memory state between them — only the DB).

---

### Task 1: Notification outbox service

**Files:**
- Create: `ticketd-api/app/services/outbox.py`
- Test: `ticketd-api/tests/test_outbox.py`

**Interfaces:**
- Produces: `async def enqueue_notification(session: AsyncSession, *,
  to_address: str, subject: str = "", body: str) -> NotificationOutbox` —
  adds a row to the session (caller controls the transaction/commit, so
  this can be called in the same transaction as the ticket update — that
  atomicity is the whole point, see `../DESIGN-async-notifications.md`).
  Phase 4 (password reset) also calls this function.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_outbox.py
import pytest
from sqlalchemy import select
from app.models import NotificationOutbox
from app.services.outbox import enqueue_notification


@pytest.mark.asyncio
async def test_enqueue_notification_creates_pending_row(db_session):
    await enqueue_notification(db_session, to_address="a@corp.example.com", body="hello")
    await db_session.flush()

    rows = (await db_session.execute(select(NotificationOutbox))).scalars().all()
    assert len(rows) == 1
    assert rows[0].to_address == "a@corp.example.com"
    assert rows[0].body == "hello"
    assert rows[0].sent_at is None
    assert rows[0].attempts == 0
```

- [ ] **Step 2: Run to verify it fails, then implement**

```python
# app/services/outbox.py
from app.models import NotificationOutbox
from sqlalchemy.ext.asyncio import AsyncSession


async def enqueue_notification(
    session: AsyncSession, *, to_address: str, body: str, subject: str = ""
) -> NotificationOutbox:
    row = NotificationOutbox(to_address=to_address, subject=subject, body=body)
    session.add(row)
    return row
```

- [ ] **Step 3: Run tests, verify pass; commit**

```bash
pytest tests/test_outbox.py -v
git add app/services/outbox.py tests/test_outbox.py
git commit -m "feat: add notification outbox enqueue service"
```

---

### Task 2: Close endpoint (the fix for the June outage)

**Files:**
- Modify: `ticketd-api/app/routes/tickets.py` — add the close route
- Test: `ticketd-api/tests/test_close_ticket.py`

**Interfaces:**
- Consumes: `app.services.outbox.enqueue_notification` (Task 1).
- Produces: `POST /api/tickets/{id}/close` → `CloseResponse`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_close_ticket.py
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.models import NotificationOutbox


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_close_open_ticket_returns_true_and_enqueues_email(client, db_session):
    created = await client.post("/api/tickets", json={"title": "Close me"})
    ticket_id = created.json()["id"]

    resp = await client.post(f"/api/tickets/{ticket_id}/close")
    assert resp.status_code == 200
    assert resp.json() == {"closed": True}

    outbox = (await db_session.execute(select(NotificationOutbox))).scalars().all()
    assert len(outbox) == 1
    assert "Close me" in outbox[0].body
    assert outbox[0].sent_at is None  # not sent inline -- that's the whole point


@pytest.mark.asyncio
async def test_close_already_closed_ticket_returns_false(client, db_session):
    created = await client.post("/api/tickets", json={"title": "Close twice"})
    ticket_id = created.json()["id"]
    await client.post(f"/api/tickets/{ticket_id}/close")

    resp = await client.post(f"/api/tickets/{ticket_id}/close")
    assert resp.json() == {"closed": False}


@pytest.mark.asyncio
async def test_close_unknown_ticket_returns_false_not_404(client):
    # matches legacy: unlike GET, close does not distinguish "not found"
    # from "already closed"
    resp = await client.post("/api/tickets/999999/close")
    assert resp.status_code == 200
    assert resp.json() == {"closed": False}


@pytest.mark.asyncio
async def test_close_does_not_call_smtp(client, db_session, monkeypatch):
    # If this test needs SMTP to be reachable to pass, the fix is broken.
    def fail_if_called(*args, **kwargs):
        raise AssertionError("close_ticket must not call SMTP directly")
    monkeypatch.setattr("smtplib.SMTP", fail_if_called)

    created = await client.post("/api/tickets", json={"title": "No SMTP here"})
    ticket_id = created.json()["id"]
    resp = await client.post(f"/api/tickets/{ticket_id}/close")
    assert resp.status_code == 200  # would raise via monkeypatch if SMTP were touched
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_close_ticket.py -v
```
Expected: FAIL — route doesn't exist (404 instead of 200).

- [ ] **Step 3: Implement — append to `app/routes/tickets.py`**

```python
from app.services.outbox import enqueue_notification
from app.schemas import CloseResponse
from sqlalchemy import update
from datetime import datetime, timezone


@router.post("/{ticket_id}/close")
async def close_ticket(ticket_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        update(Ticket)
        .where(Ticket.id == ticket_id, Ticket.status != "closed")
        .values(status="closed", closed_at=datetime.now(timezone.utc))
        .returning(Ticket.id, Ticket.title)
    )
    row = result.first()
    if row is None:
        await session.commit()  # no-op, but keep the session state consistent
        return CloseResponse(closed=False)

    # Same transaction as the status update: this is the fix. Either both
    # the close and the outbox row land, or neither does -- there is no
    # window where the ticket is closed but no notification is queued, and
    # (crucially, vs. legacy) no window where SMTP being down can fail this
    # request at all, since we never call SMTP here.
    await enqueue_notification(
        session,
        to_address="watchers@example.internal",
        body=f"closed: {row.title}",
    )
    await session.commit()
    return CloseResponse(closed=True)
```

- [ ] **Step 4: Run tests, verify pass; commit**

```bash
pytest tests/test_close_ticket.py -v
git add app/routes/tickets.py tests/test_close_ticket.py
git commit -m "feat: implement POST /api/tickets/{id}/close via outbox (fixes SMTP-blocking incident)"
```

---

### Task 3: Worker process

**Files:**
- Create: `ticketd-api/app/notify.py` (ported from legacy `app/notify.py`)
- Create: `ticketd-api/app/worker.py`
- Test: `ticketd-api/tests/test_worker.py`

**Interfaces:**
- Produces: `app.notify.send_mail(to: str, body: str) -> None` (same
  signature as legacy — kept as a thin, swappable wrapper around
  `smtplib`).
- Produces: `async def process_outbox_batch(session: AsyncSession, *,
  batch_size: int = 50) -> int` — processes one batch, returns count sent.
  This is the unit tested directly; `run_forever()` is a thin poll loop
  around it and is not unit tested (it's an infinite loop — verified via
  the load test in `../verification/`, not pytest).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_worker.py
import pytest
from sqlalchemy import select
from app.models import NotificationOutbox
from app.worker import process_outbox_batch


@pytest.mark.asyncio
async def test_process_outbox_batch_sends_and_marks_sent(db_session, monkeypatch):
    sent = []
    monkeypatch.setattr("app.worker.send_mail", lambda to, body: sent.append((to, body)))

    db_session.add(NotificationOutbox(to_address="a@corp.example.com", body="hi"))
    await db_session.flush()

    count = await process_outbox_batch(db_session)
    await db_session.commit()

    assert count == 1
    assert sent == [("a@corp.example.com", "hi")]
    row = (await db_session.execute(select(NotificationOutbox))).scalar_one()
    assert row.sent_at is not None


@pytest.mark.asyncio
async def test_process_outbox_batch_records_failure_without_crashing(db_session, monkeypatch):
    def boom(to, body):
        raise ConnectionRefusedError("smtp down")
    monkeypatch.setattr("app.worker.send_mail", boom)

    db_session.add(NotificationOutbox(to_address="a@corp.example.com", body="hi"))
    await db_session.flush()

    count = await process_outbox_batch(db_session)
    await db_session.commit()

    assert count == 0
    row = (await db_session.execute(select(NotificationOutbox))).scalar_one()
    assert row.sent_at is None
    assert row.attempts == 1
    assert "smtp down" in row.last_error


@pytest.mark.asyncio
async def test_process_outbox_batch_skips_already_sent(db_session, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setattr("app.worker.send_mail", lambda to, body: (_ for _ in ()).throw(
        AssertionError("must not resend")))
    db_session.add(NotificationOutbox(
        to_address="a@corp.example.com", body="hi", sent_at=datetime.now(timezone.utc)))
    await db_session.flush()

    count = await process_outbox_batch(db_session)
    assert count == 0


@pytest.mark.asyncio
async def test_process_outbox_batch_respects_backoff(db_session, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setattr("app.worker.send_mail", lambda to, body: (_ for _ in ()).throw(
        AssertionError("must not retry within backoff window")))
    db_session.add(NotificationOutbox(
        to_address="a@corp.example.com", body="hi",
        attempts=1, last_attempt_at=datetime.now(timezone.utc)))  # just failed; backoff is 2s
    await db_session.flush()

    count = await process_outbox_batch(db_session)
    assert count == 0  # skipped due to backoff, not attempted again immediately
```

- [ ] **Step 2: Port `app/notify.py`**

```python
# app/notify.py -- ported from legacy ticketd/app/notify.py, unchanged
# behavior. Only the caller changed (worker, not the request handler).
import smtplib
from app.config import get_settings


def send_mail(to: str, body: str) -> None:
    settings = get_settings()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
        s.sendmail("ticketd@example.internal", [to], body)
```

- [ ] **Step 3: Implement `app/worker.py`**

```python
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import async_session
from app.models import NotificationOutbox
from app.notify import send_mail

logger = logging.getLogger("ticketd.worker")

MAX_ATTEMPTS = 10
MAX_BACKOFF_SECONDS = 300


def _backoff_seconds(attempts: int) -> int:
    return min(2**attempts, MAX_BACKOFF_SECONDS)


def _eligible(row: NotificationOutbox, now: datetime) -> bool:
    if row.sent_at is not None:
        return False
    if row.attempts >= MAX_ATTEMPTS:
        return False
    if row.last_attempt_at is None:
        return True
    return now >= row.last_attempt_at + timedelta(seconds=_backoff_seconds(row.attempts))


async def process_outbox_batch(session: AsyncSession, batch_size: int = 50) -> int:
    now = datetime.now(timezone.utc)
    candidates = (
        await session.execute(
            select(NotificationOutbox)
            .where(NotificationOutbox.sent_at.is_(None))
            .order_by(NotificationOutbox.created_at)
            .limit(batch_size)
        )
    ).scalars().all()

    sent_count = 0
    for row in candidates:
        if not _eligible(row, now):
            continue
        try:
            send_mail(row.to_address, row.body)
        except Exception as exc:  # noqa: BLE001 -- must not crash the worker loop
            row.attempts += 1
            row.last_attempt_at = now
            row.last_error = str(exc)
            logger.warning("notification %s failed (attempt %s): %s", row.id, row.attempts, exc)
        else:
            row.sent_at = now
            sent_count += 1
    return sent_count


async def run_forever():
    settings = get_settings()
    while True:
        async with async_session() as session:
            sent = await process_outbox_batch(session)
            await session.commit()
        if sent:
            logger.info("sent %s notification(s)", sent)
        await asyncio.sleep(settings.outbox_poll_interval_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_forever())
```

Note: `select(...).with_for_update(skip_locked=True)` from
`../DESIGN-async-notifications.md` was simplified out of this first cut
since only one worker instance is assumed to run (see design doc — "harmless
with one"). If a second worker instance is ever deployed, add
`.with_for_update(skip_locked=True)` to the query before that happens, not
after.

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_worker.py -v
```
Expected: PASS.

- [ ] **Step 5: Manual smoke test of the poll loop** (not automated — it's
  an infinite loop by design)

```bash
python -m app.worker &
WORKER_PID=$!
# create + close a ticket via curl/httpie against the running API, wait
# ~5-10s, then check the row's sent_at
sleep 8
kill $WORKER_PID
```

- [ ] **Step 6: Commit**

```bash
git add app/notify.py app/worker.py tests/test_worker.py
git commit -m "feat: add outbox worker process (async email delivery, retry with backoff)"
```

---

## Definition of done for this phase

- `POST /api/tickets/{id}/close` never touches `smtplib` (enforced by
  `test_close_does_not_call_smtp`).
- The worker sends queued notifications, marks them sent, and records
  failures without crashing or resending.
- Run `../verification/smtp_outage_test.py` (see `../verification/`) —
  simulates SMTP being completely unreachable and asserts close-request
  latency stays low regardless. This is the direct regression test for the
  June incident and is the most important verification step in the whole
  rewrite.
