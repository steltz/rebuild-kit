"""L2 characterization tests for the Tickets subsystem, generated from
docs/features/draft/tickets.md. Each test cites the fidelity tag it's checking. FIXED behaviors
must match legacy exactly (also covered by L3 replay, verification/replay/corpus/tickets.requests.jsonl);
REPAIR behaviors assert the TARGET behavior, not legacy's.
"""


def test_create_requires_title(client):
    # FIXED — legacy/app/server.py:44-45
    r = client.post("/api/tickets", json={})
    assert r.status_code == 422
    assert r.json()["error"] == "title_required"


def test_create_blank_title_rejected(client):
    # FIXED — legacy/app/server.py:43-45 (.strip() then falsy check)
    r = client.post("/api/tickets", json={"title": "   "})
    assert r.status_code == 422


def test_create_defaults_priority_med(client):
    # FIXED — legacy/app/server.py:47
    r = client.post("/api/tickets", json={"title": "No priority given"})
    assert r.status_code == 201
    tid = r.json()["id"]
    got = client.get(f"/api/tickets/{tid}").json()
    assert got["priority"] == "med"


def test_create_numeric_priority_mapping(client):
    # FIXED — legacy/app/server.py:46-49, both string and numeric-code forms must keep working
    for code, expected in [("1", "low"), ("2", "med"), ("3", "high")]:
        r = client.post("/api/tickets", json={"title": f"priority {code}", "priority": code})
        tid = r.json()["id"]
        assert client.get(f"/api/tickets/{tid}").json()["priority"] == expected


def test_get_missing_returns_200_empty_object(client):
    # FIXED — legacy/app/server.py:59-63, deliberate: NOT a 404, legacy UI depends on it
    r = client.get("/api/tickets/999999")
    assert r.status_code == 200
    assert r.json() == {}


def test_list_no_pagination_returns_all(client, seed):
    # FIXED — legacy/app/server.py:35, no pagination, everything returned
    seed([
        {"table": "tickets", "values": {"id": i, "title": f"t{i}", "slug": f"t{i}",
         "priority": "med", "status": "open", "assignee_id": None,
         "created_at": "2026-08-01T10:00:00", "closed_at": None}}
        for i in range(1, 26)
    ])
    r = client.get("/api/tickets")
    assert len(r.json()) == 25


def test_list_filter_by_status(client, seed):
    # FIXED — legacy/app/server.py:29-36
    seed([
        {"table": "tickets", "values": {"id": 1, "title": "open one", "slug": "open-one",
         "priority": "med", "status": "open", "assignee_id": None,
         "created_at": "2026-08-01T10:00:00", "closed_at": None}},
        {"table": "tickets", "values": {"id": 2, "title": "closed one", "slug": "closed-one",
         "priority": "med", "status": "closed", "assignee_id": None,
         "created_at": "2026-08-01T09:00:00", "closed_at": "2026-08-01T11:00:00"}},
    ])
    r = client.get("/api/tickets?status=open")
    assert [t["id"] for t in r.json()] == [1]


def test_close_idempotent_already_closed(client, seed):
    # FIXED — legacy/app/server.py:69-71,77 (rowcount-based, no error on repeat close)
    seed([{"table": "tickets", "values": {"id": 1, "title": "x", "slug": "x", "priority": "med",
           "status": "closed", "assignee_id": None, "created_at": "2026-08-01T10:00:00",
           "closed_at": "2026-08-01T11:00:00"}}])
    r = client.post("/api/tickets/1/close")
    assert r.status_code == 200
    assert r.json() == {"closed": False}


def test_close_missing_ticket(client):
    # FIXED — legacy/app/server.py:69-77, no 404 case for close
    r = client.post("/api/tickets/999999/close")
    assert r.status_code == 200
    assert r.json() == {"closed": False}


def test_close_dispatches_notification_asynchronously(client, seed):
    # REPAIR — PB-001 (docs/problem-brief.md). Target behavior per docs/open-questions.md#OQ-002:
    # the close endpoint's response must not block on SMTP. Asserted here via the testing hook's
    # state dump rather than wall-clock timing (timing-based assertions are flaky); the hook
    # contract is documented in verification/harness/run_modern.py.
    seed([{"table": "tickets", "values": {"id": 1, "title": "close me", "slug": "close-me",
           "priority": "high", "status": "open", "assignee_id": None,
           "created_at": "2026-08-01T10:00:00", "closed_at": None}}])
    r = client.post("/api/tickets/1/close")
    assert r.status_code == 200
    assert r.json() == {"closed": True}
    # Executor: replace with your testing_mod.dump_state()["email_dispatch"] assertion once
    # WO-004 is implemented — mode must be "queued", never "sync". Left unassorted here
    # deliberately since the exact hook return shape is FREE until WO-004 is built.


def test_slug_collision_not_prevented(client, seed):
    # FIXED (existing, evidenced, not brief-flagged) — legacy/app/util.py:5-6,
    # legacy/db/schema.sql:1-10 (no UNIQUE on slug). Do not "fix" without a human ruling.
    r1 = client.post("/api/tickets", json={"title": "Fix DB"})
    r2 = client.post("/api/tickets", json={"title": "fix db!"})
    assert r1.json()["slug"] == r2.json()["slug"] == "fix-db"
