"""L2 characterization tests for the Tickets subsystem, generated from docs/features/draft/
tickets-crud.md + docs/contracts/schemas/*.json + verification/replay/traces/tickets-crud.jsonl.

These assert against the CONTRACT (schemas + traces), not against a running server -- they are
schema/shape assertions plus direct trace replay of the captured legacy traces, runnable standalone
(no modern/ dependency yet) via `pytest verification/characterization/`. Once modern/ exists, a
parallel `test_tickets_crud_live.py` (not written here -- that's an executor-phase WO artifact)
should drive the SAME trace file against a running modern instance and assert identical outcomes
for every FIXED behavior. This file is the frozen reference those live tests get compared to.

Requires: pytest, jsonschema (not in stdlib -- install in whatever venv runs these).
"""
import json
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "docs" / "contracts" / "schemas"
TRACES = ROOT / "verification" / "replay" / "traces" / "tickets-crud.jsonl"


def load_schema(name):
    return json.loads((SCHEMAS / name).read_text())


def load_traces():
    return [json.loads(l) for l in TRACES.read_text().splitlines() if l.strip()]


TRACE_BY_ID = {t["id"]: t for t in load_traces()}


def test_all_traces_loadable():
    assert len(TRACE_BY_ID) == 13, "expected 13 captured tickets-crud traces (see P7 capture log)"


def test_list_empty_is_array():
    t = TRACE_BY_ID["tickets-list-empty-001"]
    assert t["response"]["status"] == 200
    assert t["response"]["body"] == []


def test_create_ticket_response_matches_schema():
    schema = load_schema("create-ticket-response.json")
    t = TRACE_BY_ID["tickets-create-001"]
    assert t["response"]["status"] == 201
    jsonschema.validate(t["response"]["body"], schema)


def test_slug_collision_is_observed_not_prevented():
    """PB-003/OQ-001: legacy allows two tickets to share a slug. This test locks in the CURRENT
    (pre-ruling) behavior so an implementation doesn't accidentally start rejecting collisions
    before OQ-001 is ruled -- that would be an unsanctioned behavior change, not a bug fix."""
    a = TRACE_BY_ID["tickets-create-001"]
    b = TRACE_BY_ID["tickets-create-slug-collision-002"]
    assert a["response"]["status"] == 201
    assert b["response"]["status"] == 201
    assert a["response"]["body"]["slug"] == b["response"]["body"]["slug"] == "fix-db"
    assert a["response"]["body"]["id"] != b["response"]["body"]["id"]


def test_empty_title_rejected():
    schema = load_schema("error.json")
    for tid in ("tickets-create-empty-title-003", "tickets-create-no-body-004"):
        t = TRACE_BY_ID[tid]
        assert t["response"]["status"] == 422
        jsonschema.validate(t["response"]["body"], schema)
        assert t["response"]["body"]["error"] == "title_required"


def test_null_title_is_unhandled_500_not_422():
    """OQ-008 resolution: explicit JSON null for title is NOT the 422 title_required path -- it's
    an unhandled exception (HTML error page). Locks in the traced/evidenced behavior; if a future
    ruling on OQ-008 changes this, this test (and the trace + OQ-008 entry) must be updated
    together, not silently."""
    t = TRACE_BY_ID["tickets-create-null-title-900"]
    assert t["response"]["status"] == 500
    assert isinstance(t["response"]["body"], str)
    assert "<html" in t["response"]["body"].lower()


def test_invalid_priority_is_unhandled_500():
    t = TRACE_BY_ID["tickets-create-invalid-priority-906"]
    assert t["response"]["status"] == 500
    assert isinstance(t["response"]["body"], str)


def test_get_missing_ticket_returns_200_empty_object_not_404():
    """PB-007/FIXED -- the single most contract-sensitive assertion in this file. See
    docs/contracts/openapi.yaml's getTicket description and OQ-004 (declined-for-now proposal
    to change this to a 404)."""
    t = TRACE_BY_ID["tickets-get-missing-008"]
    assert t["response"]["status"] == 200
    assert t["response"]["body"] == {}


def test_get_ticket_found_matches_schema():
    schema = load_schema("ticket.json")
    t = TRACE_BY_ID["tickets-get-found-007"]
    assert t["response"]["status"] == 200
    jsonschema.validate(t["response"]["body"], schema)


def test_get_non_numeric_id_is_404():
    t = TRACE_BY_ID["tickets-get-non-numeric-id-009"]
    assert t["response"]["status"] == 404


def test_list_filter_by_status():
    open_t = TRACE_BY_ID["tickets-list-filter-open-010"]
    assert open_t["response"]["status"] == 200
    assert all(row["status"] == "open" for row in open_t["response"]["body"])


def test_list_filter_bogus_status_returns_empty_not_error():
    t = TRACE_BY_ID["tickets-list-filter-bogus-011"]
    assert t["response"]["status"] == 200
    assert t["response"]["body"] == []


@pytest.mark.parametrize("tid", list(TRACE_BY_ID.keys()))
def test_every_trace_response_status_is_int(tid):
    assert isinstance(TRACE_BY_ID[tid]["response"]["status"], int)
