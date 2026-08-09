"""L2 characterization tests for the Auth/Reset subsystem, generated from
docs/features/draft/auth-reset.md + verification/replay/traces/auth-reset.jsonl. See
test_tickets_crud.py's module docstring for the standalone-vs-live-modern testing split.
"""
import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "docs" / "contracts" / "schemas"
TRACES = ROOT / "verification" / "replay" / "traces" / "auth-reset.jsonl"
TRACE_BY_ID = {
    (t := json.loads(l))["id"]: t for l in TRACES.read_text().splitlines() if l.strip()
}


def load_schema(name):
    return json.loads((SCHEMAS / name).read_text())


def test_all_traces_loadable():
    assert len(TRACE_BY_ID) == 6


def test_reset_request_sends_email_and_mints_md5_token_legacy_baseline():
    t = TRACE_BY_ID["reset-request-001"]
    schema = load_schema("ok-response.json")
    assert t["response"]["status"] == 200
    jsonschema.validate(t["response"]["body"], schema)
    se = t["side_effects"]
    assert se["notification"]["sent"] is True
    assert se["notification"]["to"] == ["jdoe@corp.example.com"], (
        "notify.py:7 wraps the recipient in a list (s.sendmail(from, [to], body)) even for a "
        "single address -- this is the real captured shape, not a test bug."
    )
    assert se["notification"]["dispatch_mode"] == "sync", (
        "Legacy baseline (PB-001/ED-001b) -- modern should diverge to 'async', see "
        "test_tickets_close.py's equivalent note."
    )
    assert se["token_mechanism"]["hash_algo"] == "md5", (
        "Legacy baseline (PB-002/ED-002) -- modern should diverge to a secure mechanism, "
        "whatever WO-003 picks (FREE choice, recorded in ledger.json). This test documents "
        "what legacy does, not what modern must do."
    )


def test_confirm_success_echoes_email_and_consumes_token():
    t = TRACE_BY_ID["reset-confirm-success-002"]
    schema = load_schema("reset-confirm-response.json")
    assert t["response"]["status"] == 200
    jsonschema.validate(t["response"]["body"], schema)
    assert t["response"]["body"]["email"] == "jdoe@corp.example.com"


def test_confirm_already_consumed_and_confirm_invalid_are_identical():
    """PB-002 deliberate non-disclosure: a consumed (would-be 'expired-equivalent' at replay
    time) token and a token that never existed return the IDENTICAL body/status. This is the
    single most important assertion in this file -- do not let it regress even though the
    underlying token mechanism (WO-003) is being replaced."""
    schema = load_schema("error.json")
    consumed = TRACE_BY_ID["reset-confirm-already-consumed-003"]
    invalid = TRACE_BY_ID["reset-confirm-invalid-004"]
    for t in (consumed, invalid):
        assert t["response"]["status"] == 403
        jsonschema.validate(t["response"]["body"], schema)
        assert t["response"]["body"]["error"] == "invalid_token"
    assert consumed["response"]["body"] == invalid["response"]["body"]


def test_rate_limit_returns_429_after_three_per_hour():
    schema = load_schema("error.json")
    t = TRACE_BY_ID["reset-request-rate-limited-005"]
    assert t["response"]["status"] == 429
    jsonschema.validate(t["response"]["body"], schema)
    assert t["response"]["body"]["error"] == "rate_limited"


def test_bypass_header_defeats_rate_limit_pb008_undecided():
    """PB-008/OQ-002: documents the OBSERVED contract (bypass header works), takes no position on
    whether it SHOULD continue to. If OQ-002 is ruled to drop the bypass mechanism, this test
    must be updated as part of that ruling's spec-patch, not left silently failing."""
    t = TRACE_BY_ID["reset-request-bypass-header-006"]
    assert t["response"]["status"] == 200
    assert t["response"]["body"] == {"ok": True}
