# Auth/Reset (how it works today)

Two routes implement a self-service password reset, and there's no login system anywhere else
in this app for it to be "part of" — this is the entire auth surface. Requesting a reset
(`POST /api/auth/reset`) is rate-limited to 3 requests/hour per email, checked by counting recent
rows in `reset_tokens`. An undocumented header, `X-Internal-Bypass: 1`, skips that check
entirely, with no authentication of its own gating who can send it — see `guide/flows/` for a
walked trace and `docs/open-questions.md#OQ-001` for why this is unresolved rather than ported
or dropped outright.

**The token itself is the rewrite's other headline defect (PB-002):** it's
`MD5(email + current_timestamp)` — a hash of inputs that are either attacker-known or narrowly
guessable, not output from a secure random source. Redeeming a token
(`POST /api/auth/reset/confirm`) is where the legacy code is at its most careful: an expired
token and a nonexistent token return the byte-identical `403 {"error": "invalid_token"}` — a
deliberate non-disclosure choice, commented as such in the source
(`legacy/app/server.py:103-105`). That specific care is worth noticing, because it's the one
place legacy states its own security intent in plain language, and it must survive the MD5 fix
untouched.

See `docs/features/WO-003-auth-reset.md` for the full, cited behavior list.
