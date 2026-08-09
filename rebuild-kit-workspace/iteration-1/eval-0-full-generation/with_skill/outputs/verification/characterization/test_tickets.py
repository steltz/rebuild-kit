"""Characterization: tickets subsystem. Claim IDs reference docs/features/draft/*.md;
every test freezes an observed legacy behavior (golden run: audit/harness-baseline)."""
import uuid


def _mk(api, title=None, **extra):
    title = title or f"char ticket {uuid.uuid4().hex[:8]}"
    body = {"title": title, **extra}
    status, resp = api.call("POST", "/api/tickets", body=body)
    assert status == 201
    return resp, title


# TL-1 / TL-4: full rows, newest first
def test_list_full_rows_newest_first(api):
    created, _ = _mk(api)
    status, rows = api.call("GET", "/api/tickets")
    assert status == 200 and isinstance(rows, list)
    assert rows[0]["id"] == created["id"]
    assert {"id", "title", "slug", "priority", "status", "assignee_id",
            "created_at", "closed_at"} <= set(rows[0])


# TL-3: unknown status filter -> [] not an error
def test_list_unknown_status_filter_empty(api):
    assert api.call("GET", "/api/tickets?status=weird") == (200, [])


# TC-2 / TC-3 / TC-9: strip + 201 {id, slug}
def test_create_strips_title(api):
    resp, _ = _mk(api, title="  Padded title here  ")
    assert resp["slug"] == "padded-title-here"
    _, row = api.call("GET", f"/api/tickets/{resp['id']}")
    assert row["title"] == "Padded title here"


# TC-4: coercion table
def test_create_priority_coercion(api):
    for sent, stored in [(1, "low"), ("2", "med"), (3, "high"), ("high", "high")]:
        resp, _ = _mk(api, priority=sent)
        _, row = api.call("GET", f"/api/tickets/{resp['id']}")
        assert row["priority"] == stored, f"{sent!r} -> {row['priority']}"


def test_create_default_priority_med(api):
    resp, _ = _mk(api)
    _, row = api.call("GET", f"/api/tickets/{resp['id']}")
    assert row["priority"] == "med"


# TC-2: missing/blank title
def test_create_title_required(api):
    assert api.call("POST", "/api/tickets", body={}) == (422, {"error": "title_required"})
    assert api.call("POST", "/api/tickets", body={"title": "   "}) == \
        (422, {"error": "title_required"})


# TC-1: non-JSON body behaves like {}
def test_create_non_json_body_tolerated(api):
    assert api.call("POST", "/api/tickets", raw="not json at all") == \
        (422, {"error": "title_required"})


# TC-10: unknown fields ignored; assignee not settable via API
def test_create_ignores_unknown_fields(api):
    resp, _ = _mk(api, assignee_id=1, bogus=True)
    _, row = api.call("GET", f"/api/tickets/{resp['id']}")
    assert row["assignee_id"] is None


# TC-6 / TC-7: slug algorithm + collisions allowed (legacy behavior until OQ-001 rules)
def test_slug_collision_allowed(api):
    tag = uuid.uuid4().hex[:6]
    a, _ = _mk(api, title=f"Fix DB {tag}")
    b, _ = _mk(api, title=f"fix db! {tag}")
    assert a["slug"] == b["slug"] == f"fix-db-{tag}"


def test_slug_truncated_to_64(api):
    resp, _ = _mk(api, title="x" + "very long title " * 10)
    assert len(resp["slug"]) == 64


# TG-3: missing ticket -> 200 {}
def test_get_missing_returns_200_empty_object(api):
    assert api.call("GET", "/api/tickets/99999") == (200, {})


# CL-1 / CL-2 / CL-3: idempotent close + watcher mail
def test_close_idempotent_and_notifies(api):
    resp, title = _mk(api)
    n0 = len(api.outbox())
    assert api.call("POST", f"/api/tickets/{resp['id']}/close") == (200, {"closed": True})
    mail = api.wait_mail(n0)
    assert len(mail) == 1
    assert mail[0]["to"] == ["watchers@example.internal"]
    assert mail[0]["body"] == f"closed: {title}"
    _, row = api.call("GET", f"/api/tickets/{resp['id']}")
    assert row["status"] == "closed" and row["closed_at"]
    n1 = len(api.outbox())
    assert api.call("POST", f"/api/tickets/{resp['id']}/close") == (200, {"closed": False})
    assert api.wait_mail(n1, timeout=0.5) == []


def test_close_missing_ticket_closed_false(api):
    assert api.call("POST", "/api/tickets/99999/close") == (200, {"closed": False})
