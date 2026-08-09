# **Auth/Reset** (how it works today)

Two routes implement a password-reset *token* lifecycle — notably, no route anywhere in this
codebase actually changes a password. `confirm_reset` hands back a confirmed email address and
stops; whatever consumes that confirmation to actually let someone set a new password lives
outside this tree, or was never finished. Neither possibility is resolved by the evidence here
(`docs/open-questions.md` OQ-008) — worth knowing before you assume this subsystem is "the
whole of auth."

**Requesting a reset** (`POST /api/auth/reset`) rate-limits to 3 requests/hour per email —
unless the request carries a header, `X-Internal-Bypass: 1`, that skips the check entirely.
Nothing in the code, comments, or README explains who's supposed to send that header or why
it exists (`server.py:84`, `docs/open-questions.md` OQ-006). It's preserved as-is pending a
human ruling — not removed, not "cleaned up."

The token itself is the security review's whole complaint (PB-002): `hashlib.md5(f"{email}
{time.time()}".encode()).hexdigest()` — a fast, non-cryptographic hash of two knowable-ish
inputs, not a random secret. It's stored in a table with no primary key, no index on the token
or email columns, and no database-level expiry — the 30-minute window lives entirely in
application code, checked only when someone tries to confirm.

**Confirming** (`POST /api/auth/reset/confirm`) does one thing well worth keeping: an unknown
token and an expired token produce the *identical* `403 {"error": "invalid_token"}` — the code
comment says this is deliberate, and it is good practice (it doesn't tell an attacker which
failure mode they hit). A valid, unexpired token is deleted immediately on use (single-use) and
returns the associated email.

Full behavior detail, source-cited: `docs/features/draft/auth-reset-{request,confirm}.md`.
See `flows/password-reset.md` for a real captured request/response walkthrough.
