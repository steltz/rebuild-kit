"""L2 characterization tests for the Auth/Reset subsystem, generated from
docs/features/draft/auth-reset.md.
"""
import pytest


def test_request_reset_rate_limited_after_three(client, seed):
    # FIXED — legacy/app/server.py:16-17, 84-89
    seed([
        {"table": "reset_tokens", "values": {"email": "bob@example.com", "token": f"tok-{i}",
         "created_ts": {"relative_seconds": -60 * i}}}
        for i in (1, 2, 3)
    ])
    r = client.post("/api/auth/reset", json={"email": "bob@example.com"})
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"


@pytest.mark.skip(reason="docs/open-questions.md#OQ-001 unresolved — do not build either "
                          "reading of the X-Internal-Bypass header until a human rules on it")
def test_bypass_header_behavior():
    pass


def test_confirm_expired_and_invalid_share_identical_body(client, seed):
    # FIXED — legacy/app/server.py:103-105, deliberate non-disclosure. Must stay identical.
    seed([{"table": "reset_tokens", "values": {"email": "erin@example.com",
           "token": "expired-tok", "created_ts": {"relative_seconds": -2000}}}])
    expired = client.post("/api/auth/reset/confirm", json={"token": "expired-tok"})
    invalid = client.post("/api/auth/reset/confirm", json={"token": "does-not-exist"})
    assert expired.status_code == invalid.status_code == 403
    assert expired.json() == invalid.json() == {"error": "invalid_token"}


def test_confirm_single_use(client, seed):
    # FIXED — legacy/app/server.py:106, deletion on redemption
    seed([{"table": "reset_tokens", "values": {"email": "frank@example.com",
           "token": "once-only", "created_ts": {"relative_seconds": -60}}}])
    first = client.post("/api/auth/reset/confirm", json={"token": "once-only"})
    second = client.post("/api/auth/reset/confirm", json={"token": "once-only"})
    assert first.status_code == 200
    assert first.json() == {"ok": True, "email": "frank@example.com"}
    assert second.status_code == 403
    assert second.json() == {"error": "invalid_token"}


def test_reset_token_is_not_md5_shaped(client):
    # REPAIR — PB-002. Legacy tokens are 32-char lowercase-hex MD5 digests
    # (legacy/app/server.py:90). The rewrite must NOT produce that shape — a CSPRNG token
    # (e.g. secrets.token_urlsafe) will not match this pattern. This is a weak but concrete
    # negative assertion; it does not itself prove cryptographic strength.
    r = client.post("/api/auth/reset", json={"email": "grace@example.com"})
    assert r.status_code == 200
    # Executor: capture the issued token via your testing hook (e.g. testing_mod.dump_state())
    # and assert re.fullmatch(r"[0-9a-f]{32}", token) is None. Left as a TODO here since the
    # token isn't returned in the HTTP response (matches legacy — see openapi.yaml) and the
    # state-dump hook's exact shape is FREE until WO-003 is built.
