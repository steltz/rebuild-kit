# ticketd rewrite — Phase 2: Core Tickets API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Depends on:** Phase 1 (`01-schema-and-migration.md`) complete.
> **Read first:** `../01-CURRENT-BEHAVIOR-CONTRACT.md` sections "GET
> /api/tickets", "POST /api/tickets", "GET /api/tickets/<id>" — every
> quirk documented there for these three routes is a hard requirement, not
> a suggestion. `../DESIGN-slug-collisions.md` for the slug algorithm this
> phase implements.

**Goal:** Implement `GET /api/tickets`, `POST /api/tickets`, and
`GET /api/tickets/{id}` with byte-for-byte-compatible behavior versus
legacy, plus the slug-collision fix (one of the three named problems).

**Architecture:** A `routes/tickets.py` FastAPI router, a
`services/slugs.py` module implementing the retry-on-conflict slug
algorithm from `../DESIGN-slug-collisions.md`, and Pydantic response models
in `schemas.py` that match the legacy JSON shape exactly (`SELECT *`
equivalent — every column, snake_case, as-is).

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Pydantic v2.

## Global Constraints

- No UI changes (`../00-CONTEXT-AND-CONSTRAINTS.md`).
- `GET /api/tickets/{id}` for an unknown id returns `200 {}`, **not** 404.
  This is the single most important compatibility requirement in this
  phase — see behavior contract.
- `priority` accepts `"1"|"2"|"3"|"low"|"med"|"high"` (see behavior
  contract) and now validates: anything else is `422`, not a `500`
  (named bugfix).
- `POST /api/tickets` response returns the **actually persisted** slug
  (post-collision-handling), not a fresh recomputation.

---

### Task 1: Slug generation service (implements the named fix)

**Files:**
- Create: `ticketd-api/app/services/slugs.py`
- Test: `ticketd-api/tests/test_slugs.py`

**Interfaces:**
- Produces: `slugify(text: str) -> str` (ported unchanged from legacy
  `app/util.py` — the lossy normalization itself is not the bug, the
  missing uniqueness enforcement is).
- Produces: `async def generate_unique_slug(session: AsyncSession, title:
  str) -> str` — returns a slug guaranteed not to collide *at the moment it
  was checked*; Task 2 still must handle a race via retry-on-`IntegrityError`
  at insert time (see Step 3 below — this function alone is necessary but
  not sufficient for correctness under concurrency, which is why Task 2's
  insert logic also retries).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_slugs.py
import pytest
from app.services.slugs import slugify, generate_unique_slug
from app.models import Ticket


def test_slugify_matches_legacy_behavior():
    assert slugify("Fix DB") == "fix-db"
    assert slugify("fix db!") == "fix-db"
    assert slugify("  Weird---Chars!!@@  ") == "weird-chars"
    assert len(slugify("x" * 200)) == 64


@pytest.mark.asyncio
async def test_generate_unique_slug_no_collision(db_session):
    slug = await generate_unique_slug(db_session, "Brand New Ticket")
    assert slug == "brand-new-ticket"


@pytest.mark.asyncio
async def test_generate_unique_slug_suffixes_on_collision(db_session):
    db_session.add(Ticket(title="Fix DB", slug="fix-db", priority="med", status="open"))
    await db_session.flush()

    slug = await generate_unique_slug(db_session, "fix db!")
    assert slug == "fix-db-2"


@pytest.mark.asyncio
async def test_generate_unique_slug_suffixes_past_multiple_collisions(db_session):
    db_session.add(Ticket(title="Fix DB", slug="fix-db", priority="med", status="open"))
    db_session.add(Ticket(title="Fix DB 2", slug="fix-db-2", priority="med", status="open"))
    await db_session.flush()

    slug = await generate_unique_slug(db_session, "FIX DB")
    assert slug == "fix-db-3"
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_slugs.py -v
```
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement**

```python
# app/services/slugs.py
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Ticket


def slugify(text: str) -> str:
    # unchanged from legacy app/util.py
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:64]


async def generate_unique_slug(session: AsyncSession, title: str) -> str:
    """Best-effort collision-free slug at check time. Callers that insert
    must still handle a unique-constraint violation (see routes/tickets.py
    create_ticket) because a concurrent insert can land between this check
    and the caller's INSERT -- this function narrows the race window, it
    does not eliminate it. The DB's UNIQUE INDEX on tickets.slug is the
    actual source of truth for uniqueness."""
    base = slugify(title)
    candidate = base
    suffix = 1
    while await _slug_exists(session, candidate):
        suffix += 1
        candidate = f"{base}-{suffix}"[:64]
    return candidate


async def _slug_exists(session: AsyncSession, slug: str) -> bool:
    result = await session.execute(select(Ticket.id).where(Ticket.slug == slug).limit(1))
    return result.scalar_one_or_none() is not None
```

- [ ] **Step 4: Run tests, verify pass**

```bash
pytest tests/test_slugs.py -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/slugs.py tests/test_slugs.py
git commit -m "feat: add collision-resistant slug generation (fixes duplicate slugs)"
```

---

### Task 2: Pydantic schemas

**Files:**
- Create: `ticketd-api/app/schemas.py`

**Interfaces:**
- Produces: `TicketOut` (response model matching legacy `SELECT *` shape:
  `id, title, slug, priority, status, assignee_id, created_at, closed_at`),
  `TicketCreate` (request body: `title: str`, `priority: str | int |
  None = None`), `TicketCreateResponse` (`id: int, slug: str`),
  `CloseResponse` (`closed: bool`).

- [ ] **Step 1: Write `app/schemas.py`**

```python
from datetime import datetime
from pydantic import BaseModel


class TicketOut(BaseModel):
    id: int
    title: str
    slug: str
    priority: str
    status: str
    assignee_id: int | None
    created_at: datetime
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class TicketCreate(BaseModel):
    title: str = ""
    priority: str | int | None = None


class TicketCreateResponse(BaseModel):
    id: int
    slug: str


class CloseResponse(BaseModel):
    closed: bool
```

No test needed for pure schema declarations — behavior is covered by the
route tests in Task 3.

- [ ] **Step 2: Commit**

```bash
git add app/schemas.py
git commit -m "feat: add ticket Pydantic schemas"
```

---

### Task 3: Priority normalization + tickets router

**Files:**
- Create: `ticketd-api/app/services/priority.py`
- Create: `ticketd-api/app/routes/tickets.py`
- Modify: `ticketd-api/app/main.py` — register the router
  (`app.include_router(tickets.router)`)
- Test: `ticketd-api/tests/test_tickets_api.py`

**Interfaces:**
- Consumes: `app.services.slugs.generate_unique_slug` (Task 1),
  `app.schemas.*` (Task 2), `app.db.get_session` (Phase 0).
- Produces: `app.services.priority.normalize_priority(raw: str | int |
  None) -> str` — raises `app.services.priority.InvalidPriority` for
  anything outside `{1,2,3,low,med,high}` (Phase 3/4 don't consume this,
  but keep it a standalone function so it stays independently testable).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tickets_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.priority import normalize_priority, InvalidPriority


def test_normalize_priority_accepts_numeric_strings():
    assert normalize_priority("1") == "low"
    assert normalize_priority("2") == "med"
    assert normalize_priority("3") == "high"


def test_normalize_priority_accepts_words():
    assert normalize_priority("low") == "low"
    assert normalize_priority("high") == "high"


def test_normalize_priority_defaults_to_med():
    assert normalize_priority(None) == "med"


def test_normalize_priority_rejects_garbage():
    with pytest.raises(InvalidPriority):
        normalize_priority("urgent")


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_create_ticket_minimal(client, db_session):
    resp = await client.post("/api/tickets", json={"title": "Fix DB"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "fix-db"
    assert isinstance(body["id"], int)


@pytest.mark.asyncio
async def test_create_ticket_requires_title(client):
    resp = await client.post("/api/tickets", json={})
    assert resp.status_code == 422
    assert resp.json() == {"error": "title_required"}


@pytest.mark.asyncio
async def test_create_ticket_rejects_invalid_priority(client):
    resp = await client.post("/api/tickets", json={"title": "x", "priority": "urgent"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_ticket_dedupes_slug(client, db_session):
    r1 = await client.post("/api/tickets", json={"title": "Fix DB"})
    r2 = await client.post("/api/tickets", json={"title": "fix db!"})
    assert r1.json()["slug"] == "fix-db"
    assert r2.json()["slug"] == "fix-db-2"
    assert r1.json()["slug"] != r2.json()["slug"]


@pytest.mark.asyncio
async def test_get_unknown_ticket_returns_200_empty_object(client):
    # PRESERVE-CRITICAL: legacy UI depends on 200 {} for unknown ids, not 404
    resp = await client.get("/api/tickets/999999")
    assert resp.status_code == 200
    assert resp.json() == {}


@pytest.mark.asyncio
async def test_get_known_ticket(client, db_session):
    created = await client.post("/api/tickets", json={"title": "Findable"})
    ticket_id = created.json()["id"]
    resp = await client.get(f"/api/tickets/{ticket_id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Findable"


@pytest.mark.asyncio
async def test_list_tickets_no_pagination_by_default(client, db_session):
    for i in range(5):
        await client.post("/api/tickets", json={"title": f"t{i}"})
    resp = await client.get("/api/tickets")
    assert resp.status_code == 200
    assert len(resp.json()) >= 5  # full list, not paginated


@pytest.mark.asyncio
async def test_list_tickets_filters_by_status(client, db_session):
    created = await client.post("/api/tickets", json={"title": "will close"})
    ticket_id = created.json()["id"]
    await client.post(f"/api/tickets/{ticket_id}/close")  # Task exists in Phase 3; stub for now if not yet implemented

    open_only = await client.get("/api/tickets", params={"status": "open"})
    assert all(t["status"] == "open" for t in open_only.json())
```

Note: the last test (`test_list_tickets_filters_by_status`) calls the
`close` endpoint, which Phase 3 implements. If Phase 3 hasn't run yet when
this task is executed, comment that one test out with a `# TODO: enable
once Phase 3 lands POST /api/tickets/{id}/close` note and come back to it —
do not leave it silently skipped without the comment.

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_tickets_api.py -v
```
Expected: FAIL (no router yet).

- [ ] **Step 3: Implement `app/services/priority.py`**

```python
class InvalidPriority(ValueError):
    pass


_NUMERIC_MAP = {"1": "low", "2": "med", "3": "high"}
_VALID = {"low", "med", "high"}


def normalize_priority(raw: str | int | None) -> str:
    if raw is None:
        return "med"
    raw = str(raw)
    if raw in _NUMERIC_MAP:
        return _NUMERIC_MAP[raw]
    if raw in _VALID:
        return raw
    raise InvalidPriority(f"invalid priority: {raw!r}")
```

- [ ] **Step 4: Implement `app/routes/tickets.py`**

```python
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticket
from app.schemas import TicketCreate, TicketCreateResponse
from app.services.priority import normalize_priority, InvalidPriority
from app.services.slugs import generate_unique_slug

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("")
async def list_tickets(status: str | None = None, session: AsyncSession = Depends(get_session)):
    query = select(Ticket).order_by(Ticket.created_at.desc())
    if status:
        query = query.where(Ticket.status == status)
    rows = (await session.execute(query)).scalars().all()
    return [_ticket_to_dict(t) for t in rows]


@router.post("", status_code=201)
async def create_ticket(body: TicketCreate, session: AsyncSession = Depends(get_session)):
    title = body.title.strip()
    if not title:
        return JSONResponse(status_code=422, content={"error": "title_required"})

    try:
        priority = normalize_priority(body.priority)
    except InvalidPriority:
        return JSONResponse(status_code=422, content={"error": "invalid_priority"})

    slug = await generate_unique_slug(session, title)
    ticket = Ticket(title=title, slug=slug, priority=priority, status="open")
    session.add(ticket)
    try:
        await session.flush()
    except Exception:
        # extremely rare race: another request inserted the same slug
        # between generate_unique_slug's check and this flush. Retry once
        # with a freshly-recomputed slug (see DESIGN-slug-collisions.md).
        await session.rollback()
        slug = await generate_unique_slug(session, title)
        ticket = Ticket(title=title, slug=slug, priority=priority, status="open")
        session.add(ticket)
        await session.flush()

    await session.commit()
    return TicketCreateResponse(id=ticket.id, slug=ticket.slug)


@router.get("/{ticket_id}")
async def get_ticket(ticket_id: int, session: AsyncSession = Depends(get_session)):
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        # PRESERVE-CRITICAL: legacy returns 200 {} for unknown ids, not 404.
        return {}
    return _ticket_to_dict(ticket)


def _ticket_to_dict(t: Ticket) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "slug": t.slug,
        "priority": t.priority,
        "status": t.status,
        "assignee_id": t.assignee_id,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
    }
```

- [ ] **Step 5: Register the router in `app/main.py`**

```python
from app.routes import tickets
app.include_router(tickets.router)
```

- [ ] **Step 6: Run tests, verify pass**

```bash
pytest tests/test_tickets_api.py -v
```
Expected: PASS (except the status-filter test if Phase 3's close endpoint
isn't wired yet — see the note in Step 1).

- [ ] **Step 7: Commit**

```bash
git add app/services/priority.py app/routes/tickets.py app/main.py tests/test_tickets_api.py
git commit -m "feat: implement GET/POST /api/tickets and GET /api/tickets/{id}"
```

---

## Definition of done for this phase

- `GET /api/tickets`, `POST /api/tickets`, `GET /api/tickets/{id}` behave
  identically to legacy except: (a) invalid `priority` now returns `422`
  instead of crashing to `500`, (b) colliding slugs now get a numeric
  suffix instead of silently duplicating.
- `pytest` green, including the slug-collision and unknown-id tests.
- Run `../verification/parity_check.py` (see `../verification/`) against
  this phase's endpoints once both legacy and new servers can run
  side-by-side.
