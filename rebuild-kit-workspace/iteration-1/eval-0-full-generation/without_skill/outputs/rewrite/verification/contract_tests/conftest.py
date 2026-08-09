"""Contract-suite fixtures.

Black-box: everything goes over HTTP to TICKETD_BASE_URL. Set TICKETD_LEGACY=1 when the
target is the legacy Flask app so that tests encoding deliberate behavior changes
(@new_only) are skipped.
"""
import os
import uuid

import httpx
import pytest

BASE_URL = os.environ.get("TICKETD_BASE_URL", "http://127.0.0.1:8000")
IS_LEGACY = os.environ.get("TICKETD_LEGACY") == "1"

new_only = pytest.mark.skipif(
    IS_LEGACY, reason="encodes a deliberate rewrite CHANGE; legacy differs"
)
xfail_q1 = pytest.mark.skip(
    reason="gated on open question Q1 (slug collision policy); enable once resolved"
)

TICKET_KEYS = {
    "id", "title", "slug", "priority", "status", "assignee_id", "created_at", "closed_at",
}


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        yield c


@pytest.fixture()
def make_ticket(client):
    """Create a ticket with a unique title; returns the creation response JSON."""
    def _make(title=None, **body):
        payload = {"title": title or f"contract test {uuid.uuid4().hex[:12]}", **body}
        r = client.post("/api/tickets", json=payload)
        assert r.status_code == 201, r.text
        return payload["title"], r.json()
    return _make


def unique_email():
    return f"contract-{uuid.uuid4().hex[:10]}@example.internal"
