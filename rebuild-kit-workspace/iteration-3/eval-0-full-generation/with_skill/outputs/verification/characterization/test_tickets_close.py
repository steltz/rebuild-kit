"""L2 characterization tests for ticket close, generated from docs/features/draft/tickets-crud.md
+ verification/replay/traces/tickets-close.jsonl. See test_tickets_crud.py's module docstring for
the standalone-vs-live-modern testing split.
"""
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "docs" / "contracts" / "schemas"
TRACES = ROOT / "verification" / "replay" / "traces" / "tickets-close.jsonl"
TRACE_BY_ID = {
    (t := json.loads(l))["id"]: t for l in TRACES.read_text().splitlines() if l.strip()
}


def load_schema(name):
    return json.loads((SCHEMAS / name).read_text())


def test_all_traces_loadable():
    assert len(TRACE_BY_ID) == 3


def test_first_close_transitions_and_notifies():
    t = TRACE_BY_ID["close-first-transition-001"]
    schema = load_schema("close-ticket-response.json")
    assert t["response"]["status"] == 200
    jsonschema.validate(t["response"]["body"], schema)
    assert t["response"]["body"]["closed"] is True
    se = t["side_effects"]["notification"]
    assert se["sent"] is True
    assert se["to"] == ["watchers@example.internal"]
    assert se["dispatch_mode"] == "sync", (
        "PB-001/ED-001: legacy dispatch is synchronous. This assertion documents the LEGACY "
        "baseline this test file characterizes -- it is NOT a requirement for modern/, which "
        "should diverge here per ED-001 (expected: async). A live-modern equivalent of this test "
        "must assert dispatch_mode == 'async' and cite ED-001, not copy this assertion verbatim."
    )


def test_second_close_is_idempotent_noop_no_notification():
    t = TRACE_BY_ID["close-idempotent-noop-002"]
    assert t["response"]["status"] == 200
    assert t["response"]["body"]["closed"] is False
    assert t["side_effects"]["notification"]["sent"] is False


def test_close_nonexistent_id_indistinguishable_from_already_closed():
    t = TRACE_BY_ID["close-nonexistent-id-003"]
    assert t["response"]["status"] == 200
    assert t["response"]["body"]["closed"] is False
    assert t["side_effects"]["notification"]["sent"] is False
    # Same response shape as close-idempotent-noop-002 -- verifying the two are byte-identical is
    # the actual contract claim (docs/features/draft/tickets-crud.md), not just individually valid.
    noop = TRACE_BY_ID["close-idempotent-noop-002"]
    assert t["response"]["body"] == noop["response"]["body"]
