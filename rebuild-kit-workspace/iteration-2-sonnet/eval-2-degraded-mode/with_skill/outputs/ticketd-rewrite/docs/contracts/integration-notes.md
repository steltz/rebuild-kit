# Integration Notes

## Outbound: SMTP

- **Target:** `smtp.internal:25` (`legacy/app/notify.py:6`), plaintext, no auth, no TLS
  negotiation in the code (bare `smtplib.SMTP(...)` context manager — no `starttls()` call).
- **Timeout:** 30s connect/read timeout.
- **Retry:** none. **Circuit breaker:** none. **Error handling at call sites:** none — an
  exception from `send_mail()` propagates unhandled (Flask default 500).
- **Callers:** `close_ticket` (`legacy/app/server.py:76`, after commit),
  `request_reset` (`legacy/app/server.py:94`, after commit). Both are PB-001 sites.
- **Sandbox availability:** `smtp.internal` does not resolve/exist outside the original
  deployment network. For the replay harness (P7), this is stubbed — see
  `verification/harness/README.md` — by monkeypatching `smtplib.SMTP` during legacy boot so
  traces can be captured without a real mail server. This is a harness concern, not a spec
  change: the real legacy code is unmodified, only its network dependency is faked at the
  transport layer for local twin-boot.

## Inbound: none

No webhooks are received. All 7 routes are called directly by (presumably) a browser UI not
included in this handover — no client code was provided, so client-side assumptions (e.g. "UI
relies on getting everything and filtering client-side," `legacy/app/server.py:35`) are taken on
faith from the server-side comments, not verified against actual client code.

## Hyrum's-law looseness observed (accepted-but-undocumented input shapes)

- `priority` accepts `"1"/"2"/"3"` as aliases for `low/med/high` — not documented anywhere except
  the code comment "clients send both, both must keep working" (`legacy/app/server.py:46`). This
  is the single clearest piece of evidence in the whole app that a real, unseen client relies on
  a specific undocumented input shape — treat any future "cleanup" of this coercion as high-risk.
- `X-Internal-Bypass: 1` header — see `docs/open-questions.md#OQ-007`.
