import pytest


@pytest.mark.asyncio
async def test_create_and_get_ticket(client):
    resp = await client.post("/api/tickets", json={"title": "Fix DB"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "fix-db"

    resp = await client.get(f"/api/tickets/{body['id']}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "open"
    assert resp.json()["priority"] == "med"


@pytest.mark.asyncio
async def test_get_missing_ticket_returns_200_empty_body(client):
    # Preserved legacy quirk — see docs/OPEN_QUESTIONS.md #1.
    resp = await client.get("/api/tickets/999999")
    assert resp.status_code == 200
    assert resp.json() == {}


@pytest.mark.asyncio
async def test_create_ticket_requires_title(client):
    resp = await client.post("/api/tickets", json={"title": "   "})
    assert resp.status_code == 422
    assert resp.json() == {"error": "title_required"}


@pytest.mark.asyncio
async def test_priority_accepts_numeric_and_word_forms(client):
    resp = await client.post("/api/tickets", json={"title": "a", "priority": "3"})
    assert resp.status_code == 201
    ticket_id = resp.json()["id"]
    resp = await client.get(f"/api/tickets/{ticket_id}")
    assert resp.json()["priority"] == "high"

    resp = await client.post("/api/tickets", json={"title": "b", "priority": "low"})
    assert resp.status_code == 201
    ticket_id = resp.json()["id"]
    resp = await client.get(f"/api/tickets/{ticket_id}")
    assert resp.json()["priority"] == "low"


@pytest.mark.asyncio
async def test_close_ticket_enqueues_notification_without_blocking(client):
    resp = await client.post("/api/tickets", json={"title": "c"})
    ticket_id = resp.json()["id"]

    resp = await client.post(f"/api/tickets/{ticket_id}/close")
    assert resp.status_code == 200
    assert resp.json() == {"closed": True}

    # Closing again is a no-op, matches legacy.
    resp = await client.post(f"/api/tickets/{ticket_id}/close")
    assert resp.json() == {"closed": False}


@pytest.mark.asyncio
async def test_list_tickets_filters_by_status(client):
    await client.post("/api/tickets", json={"title": "open one"})
    resp = await client.post("/api/tickets", json={"title": "closed one"})
    await client.post(f"/api/tickets/{resp.json()['id']}/close")

    resp = await client.get("/api/tickets", params={"status": "closed"})
    assert resp.status_code == 200
    titles = [t["title"] for t in resp.json()]
    assert titles == ["closed one"]
