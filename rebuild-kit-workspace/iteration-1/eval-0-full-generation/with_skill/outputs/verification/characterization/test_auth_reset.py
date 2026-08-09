"""Characterization: auth-reset subsystem. Claim IDs in docs/features/draft/auth-reset-*.md.
Token VALUES are never asserted (PB-002 repairs the format); behaviors are."""
import re

TOKEN_RE = re.compile(r"^reset token: (.+)$", re.M)


def _request_reset(api, email, bypass=False):
    n0 = len(api.outbox())
    headers = {"X-Internal-Bypass": "1"} if bypass else None
    status, resp = api.call("POST", "/api/auth/reset", body={"email": email},
                            headers=headers)
    mail = api.wait_mail(n0) if status == 200 else []
    token = TOKEN_RE.search(mail[-1]["body"]).group(1) if mail else None
    return status, resp, token, mail


# RR-1 / RR-5-outcome / RR-7 / RC-5: full round trip
def test_reset_roundtrip_single_use(api, unique_email):
    status, resp, token, mail = _request_reset(api, unique_email)
    assert (status, resp) == (200, {"ok": True})
    assert token, "token must be delivered by mail"
    assert token not in str(resp), "token never in the response (RR-7)"
    assert mail[-1]["to"] == [unique_email]
    assert api.call("POST", "/api/auth/reset/confirm", body={"token": token}) == \
        (200, {"ok": True, "email": unique_email})
    # single-use (RC-5): same token again -> 403
    assert api.call("POST", "/api/auth/reset/confirm", body={"token": token}) == \
        (403, {"error": "invalid_token"})


# RC-2
def test_unknown_token_403(api):
    assert api.call("POST", "/api/auth/reset/confirm",
                    body={"token": "deadbeefdeadbeefdeadbeefdeadbeef"}) == \
        (403, {"error": "invalid_token"})


# RC-3: expired token -> byte-identical body to unknown token (non-disclosure)
def test_expired_token_same_body_as_invalid(api, unique_email):
    _, _, token, _ = _request_reset(api, unique_email)
    api.age_tokens(unique_email, 31 * 60)
    expired = api.call("POST", "/api/auth/reset/confirm", body={"token": token})
    unknown = api.call("POST", "/api/auth/reset/confirm", body={"token": "nope"})
    assert expired == unknown == (403, {"error": "invalid_token"})


# RR-2: 3 per rolling hour, 4th -> 429, no mail on 429
def test_rate_limit_three_per_hour(api, unique_email):
    for _ in range(3):
        status, _, _, _ = _request_reset(api, unique_email)
        assert status == 200
    n = len(api.outbox())
    assert api.call("POST", "/api/auth/reset", body={"email": unique_email}) == \
        (429, {"error": "rate_limited"})
    assert api.wait_mail(n, timeout=0.5) == []


# RR-3: bypass header skips the limit (frozen pending OQ-002)
def test_bypass_header_skips_limit(api, unique_email):
    for _ in range(3):
        _request_reset(api, unique_email)
    status, resp, token, _ = _request_reset(api, unique_email, bypass=True)
    assert (status, resp) == (200, {"ok": True}) and token


# RR-4: bypassed inserts still count toward later non-bypassed checks
def test_bypass_rows_count_toward_limit(api, unique_email):
    _request_reset(api, unique_email, bypass=True)
    assert _request_reset(api, unique_email)[0] == 200   # sees 1 prior row
    assert _request_reset(api, unique_email)[0] == 200   # sees 2
    status, _, _, _ = _request_reset(api, unique_email)  # sees 3 -> limited
    assert status == 429


# RR-1: empty email accepted and rate-limited under key ""
def test_empty_email_accepted(api):
    status, resp = api.call("POST", "/api/auth/reset", body={})
    assert (status, resp) == (200, {"ok": True})


# RR-8: multiple live tokens per email, each independently confirmable
def test_multiple_live_tokens(api, unique_email):
    _, _, t1, _ = _request_reset(api, unique_email)
    _, _, t2, _ = _request_reset(api, unique_email)
    assert t1 != t2
    assert api.call("POST", "/api/auth/reset/confirm", body={"token": t2})[0] == 200
    assert api.call("POST", "/api/auth/reset/confirm", body={"token": t1})[0] == 200
