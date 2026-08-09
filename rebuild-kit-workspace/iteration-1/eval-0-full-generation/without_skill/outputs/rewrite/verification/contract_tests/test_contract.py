"""ticketd wire-contract suite.

Run against legacy (TICKETD_LEGACY=1) first to prove these tests encode reality, then
against ticketd-ng. See ../verification.md for invocation.

NOTE for legacy runs: the legacy app sends SMTP *in-request* (close, reset). Tests touching
those endpoints need an SMTP sink reachable as smtp.internal:25 from the legacy process
(e.g. `python -m aiosmtpd -n -l 0.0.0.0:25` plus an /etc/hosts entry), otherwise legacy
500s on close-transition and reset even though the DB change commits. ticketd-ng needs no
SMTP for these tests — that asymmetry is the point of the rewrite.

The suite mutates data. Disposable databases only.
"""
import pytest

from conftest import TICKET_KEYS, new_only, unique_email, xfail_q1


# ---------------------------------------------------------------- T1: GET /api/tickets
class TestList:
    def test_returns_json_array_of_full_objects(self, client, make_ticket):
        make_ticket()
        r = client.get("/api/tickets")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and data
        assert set(data[0].keys()) == TICKET_KEYS

    def test_ordered_created_at_desc(self, client, make_ticket):
        make_ticket()
        make_ticket()
        rows = client.get("/api/tickets").json()
        stamps = [row["created_at"] for row in rows]
        assert stamps == sorted(stamps, reverse=True)

    def test_status_filter_exact_match(self, client, make_ticket):
        make_ticket()
        rows = client.get("/api/tickets", params={"status": "open"}).json()
        assert rows and all(row["status"] == "open" for row in rows)

    def test_unknown_status_returns_empty_list_not_error(self, client):
        r = client.get("/api/tickets", params={"status": "bogus"})
        assert r.status_code == 200
        assert r.json() == []


# ---------------------------------------------------------------- T2: POST /api/tickets
class TestCreate:
    def test_201_with_id_and_slug(self, client):
        r = client.post("/api/tickets", json={"title": "Fix DB"})
        assert r.status_code == 201
        body = r.json()
        assert set(body.keys()) == {"id", "slug"}
        assert isinstance(body["id"], int)
        assert body["slug"].startswith("fix-db")  # exact tail depends on Q1 policy

    def test_slugify_algorithm(self, client, make_ticket):
        title, created = make_ticket("Weird  --  Title!! 42")
        assert created["slug"].startswith("weird-title-42")

    def test_missing_title_422(self, client):
        r = client.post("/api/tickets", json={})
        assert r.status_code == 422
        assert r.json() == {"error": "title_required"}

    def test_whitespace_title_422(self, client):
        r = client.post("/api/tickets", json={"title": "   "})
        assert r.status_code == 422
        assert r.json() == {"error": "title_required"}

    def test_non_json_body_treated_as_empty(self, client):
        r = client.post(
            "/api/tickets", content=b"not json", headers={"Content-Type": "text/plain"}
        )
        assert r.status_code == 422
        assert r.json() == {"error": "title_required"}

    @pytest.mark.parametrize(
        "sent,stored",
        [
            ("1", "low"), ("2", "med"), ("3", "high"),
            (1, "low"), (2, "med"), (3, "high"),        # numeric via str()
            ("low", "low"), ("med", "med"), ("high", "high"),
        ],
    )
    def test_priority_both_client_styles(self, client, make_ticket, sent, stored):
        _, created = make_ticket(priority=sent)
        row = client.get(f"/api/tickets/{created['id']}").json()
        assert row["priority"] == stored

    def test_priority_defaults_to_med(self, client, make_ticket):
        _, created = make_ticket()
        assert client.get(f"/api/tickets/{created['id']}").json()["priority"] == "med"

    def test_extra_body_keys_ignored(self, client, make_ticket):
        _, created = make_ticket(status="closed", assignee_id=999, id=1)
        row = client.get(f"/api/tickets/{created['id']}").json()
        assert row["status"] == "open"
        assert row["assignee_id"] is None

    @new_only  # legacy 500s (SQLite CHECK violation); ng returns a clean 422 (Q6)
    def test_invalid_priority_422(self, client):
        r = client.post("/api/tickets", json={"title": "x", "priority": "urgent"})
        assert r.status_code == 422
        assert r.json() == {"error": "invalid_priority"}

    @xfail_q1
    def test_colliding_titles_get_distinct_slugs(self, client, make_ticket):
        _, a = make_ticket("Collide Me")
        _, b = make_ticket("collide me!")
        assert a["slug"] != b["slug"]


# ---------------------------------------------------------------- T3: GET /api/tickets/{id}
class TestGet:
    def test_found_returns_full_object(self, client, make_ticket):
        title, created = make_ticket()
        r = client.get(f"/api/tickets/{created['id']}")
        assert r.status_code == 200
        row = r.json()
        assert set(row.keys()) == TICKET_KEYS
        assert row["title"] == title
        assert row["closed_at"] is None

    def test_missing_id_returns_200_empty_object_not_404(self, client):
        r = client.get("/api/tickets/99999999")
        assert r.status_code == 200
        assert r.json() == {}

    def test_non_integer_id_is_404(self, client):
        assert client.get("/api/tickets/abc").status_code == 404


# ------------------------------------------------------- T4: POST /api/tickets/{id}/close
class TestClose:
    def test_close_then_reclose(self, client, make_ticket):
        _, created = make_ticket()
        tid = created["id"]
        r1 = client.post(f"/api/tickets/{tid}/close")
        assert r1.status_code == 200 and r1.json() == {"closed": True}
        row = client.get(f"/api/tickets/{tid}").json()
        assert row["status"] == "closed" and row["closed_at"] is not None
        r2 = client.post(f"/api/tickets/{tid}/close")
        assert r2.status_code == 200 and r2.json() == {"closed": False}

    def test_close_nonexistent_is_closed_false_not_404(self, client):
        r = client.post("/api/tickets/99999999/close")
        assert r.status_code == 200
        assert r.json() == {"closed": False}


# ---------------------------------------------------------------- T5: POST /api/auth/reset
class TestReset:
    def test_ok_true_for_any_email(self, client):
        r = client.post("/api/auth/reset", json={"email": unique_email()})
        assert r.status_code == 200
        assert r.json() == {"ok": True}

    def test_rate_limit_fourth_within_hour_is_429(self, client):
        email = unique_email()
        for _ in range(3):
            assert client.post("/api/auth/reset", json={"email": email}).status_code == 200
        r = client.post("/api/auth/reset", json={"email": email})
        assert r.status_code == 429
        assert r.json() == {"error": "rate_limited"}

    def test_rate_limit_is_per_email(self, client):
        email = unique_email()
        for _ in range(3):
            client.post("/api/auth/reset", json={"email": email})
        assert client.post(
            "/api/auth/reset", json={"email": unique_email()}
        ).status_code == 200


# -------------------------------------------------------- T6: POST /api/auth/reset/confirm
class TestConfirm:
    def test_invalid_token_403(self, client):
        r = client.post("/api/auth/reset/confirm", json={"token": "definitely-wrong"})
        assert r.status_code == 403
        assert r.json() == {"error": "invalid_token"}

    def test_missing_token_403_same_body(self, client):
        r = client.post("/api/auth/reset/confirm", json={})
        assert r.status_code == 403
        assert r.json() == {"error": "invalid_token"}

    # Full round-trip (valid token -> 200 {"ok": true, "email": ...}, second use -> 403)
    # requires reading the token out of the outbound email, which a black-box HTTP suite
    # cannot do. Covered by checklist V-9 / the ng integration tests (mailpit API).


# ---------------------------------------------------------------- T7: removed endpoints
class TestRemoved:
    @new_only  # legacy serves it; ng drops it (Q3)
    def test_internal_export_csv_gone(self, client):
        assert client.get("/internal/export/csv").status_code == 404


# ---------------------------------------------------------------- T8: error envelope
class TestErrorShapes:
    def test_no_fastapi_detail_envelope_on_contract_errors(self, client):
        r = client.post("/api/tickets", json={})
        assert "detail" not in r.json()
