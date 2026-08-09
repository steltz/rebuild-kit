# ticketd rewrite — Phase 5: CSV Export + Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Depends on:** Phase 4 (`04-secure-password-reset.md`) complete.
> **Before Task 1:** check whether `../03-OPEN-QUESTIONS.md` item 5
> (keep or drop CSV export) has been answered. If nobody answered it,
> the default is "keep" — do Task 1. If the answer comes back "drop,"
> skip Task 1 entirely and note that decision in this file's own
> checklist so a later reader knows it was a deliberate skip, not an
> oversight.

**Goal:** Port the low-traffic/low-priority `GET /internal/export/csv`
endpoint (if kept) and do the cross-cutting cleanup that doesn't belong to
any single named fix: consistent error handling, OpenAPI docs sanity check,
removing dead-code carryover risk (`legacy_import.py` — confirmed not
ported, nothing to do here, just a checklist line to close the loop).

**Architecture:** No new architecture — this phase is small and additive.

**Tech Stack:** FastAPI, `csv`/`io` stdlib.

## Global Constraints

- Same output format as legacy: `id,title,status` header-less... actually
  legacy's first line **is** a header (`"id,title,status"` is both the
  literal header row and, confusingly, looks like it could be data — see
  behavior contract: the legacy code does
  `["id,title,status"] + [f"{r['id']},{r['title']},{r['status']}" for r in
  rows]`, i.e. yes, a real header row followed by data rows). Match this
  exactly, including `Content-Type: text/csv` and no quoting/escaping of
  commas in titles (legacy doesn't escape them either — a title containing
  a comma would already produce malformed CSV today; do not "fix" this
  silently, since nothing currently depends on titles with commas working
  and there's no report of it being a problem — flag it as a known
  pre-existing limitation instead of unilaterally changing the output
  format).

---

### Task 1: CSV export endpoint (only if kept — see header note above)

**Files:**
- Create: `ticketd-api/app/routes/export.py`
- Modify: `ticketd-api/app/main.py` — register the router
- Test: `ticketd-api/tests/test_export.py`

**Interfaces:**
- Produces: `GET /internal/export/csv` → `text/csv` body.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_export.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_export_csv_matches_legacy_format(db_session):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post("/api/tickets", json={"title": "Export me"})
        resp = await client.get("/internal/export/csv")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    lines = resp.text.strip().split("\n")
    assert lines[0] == "id,title,status"
    assert any("Export me,open" in line for line in lines[1:])
```

- [ ] **Step 2: Run to verify failure, then implement**

```python
# app/routes/export.py
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Ticket

router = APIRouter(prefix="/internal/export", tags=["export"])


@router.get("/csv")
async def export_csv(session: AsyncSession = Depends(get_session)):
    rows = (await session.execute(select(Ticket))).scalars().all()
    lines = ["id,title,status"] + [f"{t.id},{t.title},{t.status}" for t in rows]
    return PlainTextResponse("\n".join(lines), media_type="text/csv")
```

- [ ] **Step 3: Register router, run tests, commit**

```python
# app/main.py
from app.routes import export
app.include_router(export.router)
```

```bash
pytest tests/test_export.py -v
git add app/routes/export.py app/main.py tests/test_export.py
git commit -m "feat: port CSV export endpoint (low-traffic, kept for parity)"
```

---

### Task 2: OpenAPI sanity pass

**Files:** none created — this is a manual review step.

- [ ] **Step 1: Start the app and check the generated docs**

```bash
uvicorn app.main:app --reload
```
Open `http://localhost:8000/docs`. Confirm all 6 (or 7, if CSV export was
kept) endpoints are listed with the right methods and paths, and that none
of the "quirk" behaviors (200-empty-object, priority int-or-string) got
accidentally over-constrained by Pydantic in a way that would reject inputs
legacy accepted. In particular double check `TicketCreate.priority: str |
int | None` still accepts a raw JSON integer `2` in the request body (not
just the string `"2"`), since real UI clients may send either — the
behavior contract only confirms clients send both forms as strings via the
access log's opacity (bodies aren't logged), but the legacy code's
`str(body.get("priority", "med"))` coercion suggests both raw ints and
strings were anticipated. Add a quick manual `curl` check:

```bash
curl -X POST localhost:8000/api/tickets -H 'content-type: application/json' -d '{"title":"t","priority":2}'
curl -X POST localhost:8000/api/tickets -H 'content-type: application/json' -d '{"title":"t","priority":"2"}'
```
Both should succeed and produce `priority: "med"`.

- [ ] **Step 2: Note the legacy_import.py decision explicitly**

Confirm (no action needed, just confirm and check this box) that
`app/legacy_import.py` was intentionally not ported — it's dead code per
both the source comment and a grep for callers. This box exists so a future
reader doesn't wonder if it was forgotten.

---

## Definition of done for this phase

- CSV export present (or explicitly, deliberately skipped per the open
  question) with a note in this file about which happened and why.
- Manual OpenAPI + curl check confirms `priority` accepts both JSON int and
  string forms.
- `legacy_import.py` confirmed and documented as intentionally not ported.
