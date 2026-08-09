"""
Parity tests against docs/01-LEGACY-BEHAVIOR-INVENTORY.md. Each test cites
the legacy source line it's protecting.
"""
from app.models import NotificationOutbox


def test_create_ticket_numeric_priority(client):
    # server.py:47-49 — "1"/"2"/"3" must map to low/med/high
    r = client.post("/api/tickets", json={"title": "Fix DB", "priority": "1"})
    assert r.status_code == 201
    body = r.json()
    assert body["slug"] == "fix-db"

    r2 = client.get(f"/api/tickets/{body['id']}")
    assert r2.json()["priority"] == "low"


def test_create_ticket_string_priority(client):
    r = client.post("/api/tickets", json={"title": "Другой тикет", "priority": "high"})
    assert r.status_code == 201


def test_create_ticket_requires_title(client):
    # server.py:44-45
    r = client.post("/api/tickets", json={"title": "   "})
    assert r.status_code == 422
    assert r.json()["detail"] == {"error": "title_required"}


def test_missing_ticket_returns_200_empty_object(client):
    # server.py:62-63 — deliberate quirk, NOT 404
    r = client.get("/api/tickets/999999")
    assert r.status_code == 200
    assert r.json() == {}


def test_list_tickets_no_pagination(client):
    for i in range(5):
        client.post("/api/tickets", json={"title": f"t{i}"})
    r = client.get("/api/tickets")
    assert r.status_code == 200
    assert len(r.json()) == 5


def test_close_ticket_enqueues_outbox_instead_of_sending(client, db_session):
    # Fix for Known Problem #1 — closing a ticket must not attempt SMTP
    # inline; it must only write an outbox row.
    created = client.post("/api/tickets", json={"title": "close me"}).json()
    r = client.post(f"/api/tickets/{created['id']}/close")
    assert r.status_code == 200
    assert r.json() == {"closed": True}

    outbox = db_session.query(NotificationOutbox).all()
    assert len(outbox) == 1
    assert outbox[0].sent_at is None
    assert "close me" in outbox[0].body


def test_close_already_closed_ticket_is_noop(client):
    # server.py:69-70 — AND status != 'closed'
    created = client.post("/api/tickets", json={"title": "t"}).json()
    client.post(f"/api/tickets/{created['id']}/close")
    r = client.post(f"/api/tickets/{created['id']}/close")
    assert r.json() == {"closed": False}
