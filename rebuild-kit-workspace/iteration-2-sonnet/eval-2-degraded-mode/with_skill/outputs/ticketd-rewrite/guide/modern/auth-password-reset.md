# Auth / Password Reset (designed-not-built)

**Designed, not built** — `WO-003` implements this, and it's gated: `verification/replay/
expected-divergences.yaml`'s ED-001b and ED-002 are currently UNSIGNED, meaning a human has not
yet formally ruled on the exact target behavior. Read `docs/features/WO-003-auth-reset.md`'s
"STOP before implementing" section before starting this WO.

As designed: token generation moves from `MD5(email+time)` to a CSPRNG
(`secrets.token_urlsafe` or equivalent) — PB-002's REPAIR. Email dispatch for the reset-request
route moves out of the request/response cycle — PB-001's second REPAIR site. Everything else
(rate limiting, the undocumented bypass header pending `OQ-007`'s ruling, the deliberately
identical expired/invalid error body) carries forward unchanged — this is the one route in the
app where "don't touch what isn't named" matters most, because it's tempting to also "fix" the
bypass header or the lack of email validation while you're in here. Don't, without a ruling.
